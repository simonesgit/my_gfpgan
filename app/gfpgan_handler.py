import os
import torch
import cv2
import numpy as np
from gfpgan import GFPGANer
import logging

logger = logging.getLogger(__name__)

class GFPGANHandler:
    def __init__(self):
        logger.info("Initializing GFPGAN model")
        try:
            self.model = GFPGANer(
                model_path='experiments/pretrained_models/GFPGANv1.4.pth',
                upscale=2,
                arch='clean',
                channel_multiplier=2,
                bg_upsampler=None
            )
            logger.info("Model initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing model: {str(e)}")
            raise

    def process_image(self, input_path, output_path):
        try:
            logger.info(f"Reading image from {input_path}")
            img = cv2.imread(input_path, cv2.IMREAD_COLOR)
            if img is None:
                logger.error("Failed to read input image")
                return False
            
            logger.info("Running GFPGAN enhancement")
            _, _, restored_img = self.model.enhance(
                img, has_aligned=False, only_center_face=False, paste_back=True
            )
            
            if restored_img is None:
                logger.error("GFPGAN enhancement returned None")
                return False
            
            logger.info(f"Saving result to {output_path}")
            cv2.imwrite(output_path, restored_img)
            
            if not os.path.exists(output_path):
                logger.error("Failed to save output image")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error in process_image: {str(e)}")
            return False