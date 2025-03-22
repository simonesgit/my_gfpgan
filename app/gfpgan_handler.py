import os
import torch
from gfpgan import GFPGANer
import cv2
import numpy as np

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
        # Read image
        img = cv2.imread(input_path, cv2.IMREAD_COLOR)
        
        # Process the image using GFPGAN
        _, _, restored_img = self.model.enhance(
            img, has_aligned=False, only_center_face=False, paste_back=True
        )
        
        # Save the result
        if restored_img is not None:
            cv2.imwrite(output_path, restored_img)
            return True
        return False