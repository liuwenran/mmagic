# Copyright (c) OpenMMLab. All rights reserved.
import os
import warnings
import torch
from typing import Dict, List, Optional, Union

from mmedit.apis.inferencers import MMEditInferencer
from mmedit.apis.inferencers.base_mmedit_inferencer import InputsType
from mmedit.utils import register_all_modules


class MMEdit:
    """MMEdit API for mmediting models inference.

    Args:
        model_name (str): Name of the editing model. Default to 'FCE_IC15'.
        model_config (str): Path to the config file for the editing model.
            Default to None.
        model_ckpt (str): Path to the checkpoint file for the editing model.
            Default to None.
        config_dir (str): Path to the directory containing config files.
            Default to 'configs/'.
        device (torch.device): Device to use for inference. Default to 'cuda'.
    """

    def __init__(self,
                 model_name: str = None,
                 model_version: str = 'a',
                 model_config: str = None,
                 model_ckpt: str = None,
                 device: torch.device = 'cuda',
                 **kwargs) -> None:

        register_all_modules(init_default_scope=True)
        inferencer_kwargs = {}
        inferencer_kwargs.update(
            self._get_inferencer_kwargs(model_name, model_version, model_config, model_ckpt))
        self.inferencer = MMEditInferencer(device=device, **inferencer_kwargs)

    def _get_inferencer_kwargs(self, model: Optional[str], model_version: Optional[str],
                               config: Optional[str], ckpt: Optional[str]) -> Dict:
        """Get the kwargs for the inferencer."""
        kwargs = {}

        if model is not None:
            cfgs = self.get_model_config(model)
            kwargs['type'] = cfgs['type']
            kwargs['config'] = os.path.join('configs/', cfgs['version'][model_version]['config'])
            kwargs['ckpt'] = cfgs['version'][model_version]['ckpt']
            # kwargs['ckpt'] = 'https://download.openmmlab.com/' + \
                # f'mmediting/{cfgs["version"][model_version]["ckpt"]}'

        if config is not None:
            if kwargs.get('config', None) is not None:
                warnings.warn(
                    f'{model}\'s default config is overridden by {config}',
                    UserWarning)
            kwargs['config'] = config

        if ckpt is not None:
            if kwargs.get('ckpt', None) is not None:
                warnings.warn(
                    f'{model}\'s default checkpoint is overridden by {ckpt}',
                    UserWarning)
            kwargs['ckpt'] = ckpt
        return kwargs

    def infer(self,
                 img: InputsType = None,
                 video: InputsType = None,
                 label: InputsType = None,
                 trimap: InputsType = None,
                 mask: InputsType = None,
                 result_out_dir: str = '',
                 show: bool = False,
                 print_result: bool = False,
                 pred_out_file: str = '',
                 **kwargs) -> Union[Dict, List[Dict]]:
        """Inferences edit model on an image(video) or a
        folder of images(videos).

        Args:
            imgs (str or np.array or Sequence[str or np.array]): Img,
                folder path, np array or list/tuple (with img
                paths or np arrays).
            result_out_dir (str): Output directory of images. Defaults to ''.
            show (bool): Whether to display the image in a popup window.
                Defaults to False.
            print_result (bool): Whether to print the results.
            pred_out_file (str): File to save the inference results. If left as
                empty, no file will be saved.

        Returns:
            Dict or List[Dict]: Each dict contains the inference result of
            each image. Possible keys are "det_polygons", "det_scores",
            "rec_texts", "rec_scores", "kie_labels", "kie_scores",
            "kie_edge_labels" and "kie_edge_scores".
        """
        return self.inferencer(
            img=img,
            video=video,
            label=label,
            trimap=trimap,
            mask=mask,
            result_out_dir=result_out_dir,
            show=show,
            print_result=print_result,
            pred_out_file=pred_out_file,
            **kwargs)

    def get_model_config(self, model_name: str) -> Dict:
        """Get the model configuration including model config and checkpoint
        url.

        Args:
            model_name (str): Name of the model.
        Returns:
            dict: Model configuration.
        """
        model_dict = {
            # conditional models
            'biggan': {
                'type':'conditional',
                'version': {
                    'a': {
                        'config':
                        'biggan/dbnet_resnet18_fpnc_1200e_icdar2015.py',
                        'ckpt':
                        'ckpt/conditional/biggan_cifar10_32x32_b25x2_500k_20210728_110906-08b61a44.pth'  
                    },
                    'b': {
                        'config':
                        'biggan/biggan_ajbrock-sn_8xb32-1500kiters_imagenet1k-128x128.py',
                        'ckpt':
                        'ckpt/conditional/biggan_imagenet1k_128x128_b32x8_best_fid_iter_1232000_20211111_122548-5315b13d.pth'
                    }
                },

            },

            # unconditional models
            'styleganv1': {
                'type': 'unconditional',
                'version': {
                    'a': {
                        'config':
                        'styleganv1/styleganv1_ffhq-256x256_8xb4-25Mimgs.py',
                        'ckpt':
                        'ckpt/unconditional/styleganv1_ffhq_256_g8_25Mimg_20210407_161748-0094da86.pth'
                    }
                }
            },

            # matting models
            'gca': {
                'type': 'matting',
                'version': {
                    'a': {
                        'config':
                        'gca/gca_r34_4xb10-200k_comp1k.py',
                        'ckpt':
                        'ckpt/matting/gca/gca_r34_4x10_200k_comp1k_SAD-33.38_20220615-65595f39.pth'
                    }
                }
            },

            # inpainting models
            'aot_gan': {
                'type': 'inpainting',
                'version': {
                    'a': {
                        'config':
                        'aot_gan/aot-gan_smpgan_4xb4_places-512x512.py',
                        'ckpt':
                        'ckpt/inpainting/AOT-GAN_512x512_4x12_places_20220509-6641441b.pth'
                    }
                }
            },

            # translation models
            'pix2pix': {
                'type': 'translation',
                'version': {
                    'a': {
                        'config':
                        'pix2pix/pix2pix_vanilla-unet-bn_1xb1-80kiters_facades.py',
                        'ckpt':
                        'ckpt/translation/pix2pix_vanilla_unet_bn_1x1_80k_facades_20210902_170442-c0958d50.pth'
                    }
                }
            },

            # restoration models
            # real_esrgan error
            'real_esrgan': {
                'type': 'restoration',
                'version': {
                    'a': {
                        'config':
                        'real_esrgan/realesrnet_c64b23g32_4xb12-lr2e-4-1000k_df2k-ost.py',
                        'ckpt':
                        'ckpt/restoration/realesrnet_c64b23g32_12x4_lr2e-4_1000k_df2k_ost_20210816-4ae3b5a4.pth'
                    },
                }
            },
            'esrgan': {
                'type': 'restoration',
                'version': {
                    'a': {
                        'config':
                        'esrgan/esrgan_psnr-x4c64b23g32_1xb16-1000k_div2k.py',
                        'ckpt':
                        'ckpt/restoration/esrgan_psnr_x4c64b23g32_1x16_1000k_div2k_20200420-bf5c993c.pth'
                    }
                }
            },

            # video_restoration models
            # basicvsr error
            'basicvsr': {
                'type': 'video_restoration',
                'version': {
                    'a': {
                        'config':
                        'basicvsr/basicvsr_2xb4_vimeo90k-bi.py',
                        'ckpt':
                        ''
                    },
                    'b': {
                        'config':
                        'basicvsr/basicvsr_2xb4_reds4.py',
                        'ckpt':
                        'ckpt/video_restoration/basicvsr_reds4_20120409-0e599677.pth'
                    }
                }
            },

            # video_interpolation models
            'flavr': {
                'type': 'video_interpolation',
                'version': {
                    'a': {
                        'config':
                        'flavr/flavr_in4out1_8xb4_vimeo90k-septuplet.py',
                        'ckpt':
                        'ckpt/video_interpolation/flavr_in4out1_g8b4_vimeo90k_septuplet_20220509-c2468995.pth'
                    }
                }
            }

        }

        if model_name not in model_dict:
            raise ValueError(f'Model {model_name} is not supported.')
        else:
            return model_dict[model_name]
