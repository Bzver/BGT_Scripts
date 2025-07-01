import torch

if torch.cuda.is_available():
    print("GPU is available")
    print(torch.cuda.device_count())
    print(torch.cuda.get_device_name())
    print(torch.cuda.get_device_properties(0))
else:
    print("GPU is not available")