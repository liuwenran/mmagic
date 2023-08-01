# Copyright (c) OpenMMLab. All rights reserved.
from abc import ABCMeta
from collections import defaultdict
from copy import deepcopy
from typing import List, Optional

import torch.nn as nn
from mmengine.model import BaseModel, is_model_wrapper

from mmagic.registry import MODELS


@MODELS.register_module()
class BaseTranslationModel(BaseModel, metaclass=ABCMeta):
    """Base Translation Model.

    Translation models can transfer images from one domain to
    another. Domain information like `default_domain`,
    `reachable_domains` are needed to initialize the class.
    And we also provide query functions like `is_domain_reachable`,
    `get_other_domains`.

    You can get a specific generator based on the domain,
    and by specifying `target_domain` in the forward function,
    you can decide the domain of generated images.
    Considering the difference among different image translation models,
    we only provide the external interfaces mentioned above.
    When you implement image translation with a specific method,
    you can inherit both `BaseTranslationModel`
    and the method (e.g BaseGAN) and implement abstract methods.

    Args:
        default_domain (str): Default output domain.
        reachable_domains (list[str]): Domains that can be generated by
            the model.
        related_domains (list[str]): Domains involved in training and
            testing. `reachable_domains` must be contained in
            `related_domains`. However, related_domains may contain
            source domains that are used to retrieve source images from
            data_batch but not in reachable_domains.
        discriminator_steps (int): The number of times the discriminator is
            completely updated before the generator is updated. Defaults to 1.
        disc_init_steps (int): The number of initial steps used only to train
            discriminators.
    """

    def __init__(self,
                 generator,
                 discriminator,
                 default_domain: str,
                 reachable_domains: List[str],
                 related_domains: List[str],
                 data_preprocessor,
                 discriminator_steps: int = 1,
                 disc_init_steps: int = 0,
                 real_img_key: str = 'real_img',
                 loss_config: Optional[dict] = None):
        super().__init__(data_preprocessor)
        self._default_domain = default_domain
        self._reachable_domains = reachable_domains
        self._related_domains = related_domains
        assert self._default_domain in self._reachable_domains
        assert set(self._reachable_domains) <= set(self._related_domains)

        self.discriminator_steps = discriminator_steps
        self.disc_init_steps = disc_init_steps
        self.real_img_key = real_img_key

        self._gen_cfg = deepcopy(generator)
        # build domain generators
        self.generators = nn.ModuleDict()
        for domain in self._reachable_domains:
            self.generators[domain] = MODELS.build(generator)

        self._disc_cfg = deepcopy(discriminator)
        # build domain discriminators
        if discriminator is not None:
            self.discriminators = nn.ModuleDict()
            for domain in self._reachable_domains:
                self.discriminators[domain] = MODELS.build(discriminator)
        # support no discriminator in testing
        else:
            self.discriminators = None

        self.loss_config = dict() if loss_config is None else loss_config

    def init_weights(self):
        """Initialize weights for the module dict.

        Args:
            pretrained (str, optional): Path for pretrained weights. If given
                None, pretrained weights will not be loaded. Default: None.
        """
        self._params_init_info = defaultdict(dict)

        for _, param in self.named_parameters():
            self._params_init_info[param][
                'init_info'] = f'The value is the same before and ' \
                                f'after calling `init_weights` ' \
                                f'of {self.__class__.__name__} '
            mean = param.data.mean().cpu()
            self._params_init_info[param]['tmp_mean_value'] = mean

        for domain in self._reachable_domains:
            if is_model_wrapper(self.generators):
                gen = self.generators.module[domain]
            else:
                gen = self.generators[domain]
            gen._params_init_info = self._params_init_info
            gen.init_weights()

            if self.discriminators is not None:
                if is_model_wrapper(self.discriminators):
                    disc = self.discriminators.module[domain]
                else:
                    disc = self.discriminators[domain]
                disc._params_init_info = self._params_init_info
                disc.init_weights()

        super()._dump_init_info()
        for m in self.modules():
            if hasattr(m, '_params_init_info'):
                del m._params_init_info

    def get_module(self, module):
        """Get `nn.ModuleDict` to fit the `MMDistributedDataParallel`
        interface.

        Args:
            module (MMDistributedDataParallel | nn.ModuleDict): The input
                module that needs processing.

        Returns:
            nn.ModuleDict: The ModuleDict of multiple networks.
        """
        if is_model_wrapper(module):
            return module.module

        return module

    def forward(self, img, test_mode=False, **kwargs):
        """Forward function.

        Args:
            img (tensor): Input image tensor.
            test_mode (bool): Whether in test mode or not. Default: False.
            kwargs (dict): Other arguments.
        """
        if not test_mode:
            return self.forward_train(img, **kwargs)

        return self.forward_test(img, **kwargs)

    def forward_train(self, img, target_domain, **kwargs):
        """Forward function for training.

        Args:
            img (tensor): Input image tensor.
            target_domain (str): Target domain of output image.
            kwargs (dict): Other arguments.

        Returns:
            dict: Forward results.
        """
        target = self.translation(img, target_domain=target_domain, **kwargs)
        results = dict(source=img, target=target)
        return results

    def forward_test(self, img, target_domain, **kwargs):
        """Forward function for testing.

        Args:
            img (tensor): Input image tensor.
            target_domain (str): Target domain of output image.
            kwargs (dict): Other arguments.

        Returns:
            dict: Forward results.
        """
        target = self.translation(img, target_domain=target_domain, **kwargs)
        results = dict(source=img.cpu(), target=target.cpu())
        return results

    def is_domain_reachable(self, domain):
        """Whether image of this domain can be generated."""
        return domain in self._reachable_domains

    def get_other_domains(self, domain):
        """get other domains."""
        return list(set(self._related_domains) - set([domain]))

    def _get_target_generator(self, domain):
        """get target generator."""
        assert self.is_domain_reachable(
            domain
        ), f'{domain} domain is not reachable, available domain list is\
            {self._reachable_domains}'

        return self.get_module(self.generators)[domain]

    def _get_target_discriminator(self, domain):
        """get target discriminator."""
        assert self.is_domain_reachable(
            domain
        ), f'{domain} domain is not reachable, available domain list is\
            {self._reachable_domains}'

        return self.get_module(self.discriminators)[domain]

    def translation(self, image, target_domain=None, **kwargs):
        """Translation Image to target style.

        Args:
            image (tensor): Image tensor with a shape of (N, C, H, W).
            target_domain (str, optional): Target domain of output image.
                Default to None.

        Returns:
            dict: Image tensor of target style.
        """
        if target_domain is None:
            target_domain = self._default_domain
        _model = self._get_target_generator(target_domain)
        outputs = _model(image, **kwargs)
        return outputs
