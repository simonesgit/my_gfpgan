import os
import torch
from gfpgan import GFPGANer

class GFPGANHandler:
    def __init__(self):
        self.model = GFPGANer(
            model_path='experiments/pretrained_models/GFPGANv1.4.pth',
            upscale=2,
            arch='clean',
            channel_multiplier=2,
            bg_upsampler=None
        )

    def process_image(self, input_path, output_path):
        # Process the image using GFPGAN
        cropped_faces, restored_faces, restored_img = self.model.enhance(
            input_path, has_aligned=False, only_center_face=False, paste_back=True
        )
        # Save the result
        if restored_img is not None:
            torch.save(restored_img, output_path)