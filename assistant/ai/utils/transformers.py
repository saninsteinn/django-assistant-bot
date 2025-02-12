import logging

import torch


logger = logging.getLogger(__name__)


def get_torch_device() -> str:
    """
    Get the device to use for PyTorch operations.
    @return: The device to use.
    """
    if torch.cuda.is_available():
        logger.info("CUDA device is available.")
        device = "cuda"
    elif torch.backends.mps.is_available() and torch.backends.mps.is_built():  # Check for Apple M1/M2 GPU support
        logger.info("MPS device is available.")
        device = "mps"
    else:
        logger.warning("CPU device is used.")
        device = "cpu"
    return device
