import os
import sys
from transformers import AutoTokenizer, AutoModel, AutoModelForCausalLM

sys.path.append(os.path.join(os.path.realpath(os.path.dirname(__file__)), '..'))

from models import embedder_models, provider_models


for model in embedder_models:
    try:
        AutoTokenizer.from_pretrained(model, local_files_only=True)
        AutoModel.from_pretrained(model, local_files_only=True)#.to("mps")
        print(f"Model {model} is already loaded")
    except EnvironmentError:
        print(f"Loading {model} from Hugging Face")
        AutoTokenizer.from_pretrained(model)
        AutoModel.from_pretrained(model)


for model in provider_models:
    try:
        AutoTokenizer.from_pretrained(model, local_files_only=True)
        AutoModelForCausalLM.from_pretrained(model, local_files_only=True)#.to("mps")
        print(f"Model {model} is already loaded")
    except EnvironmentError:
        print(f"Loading {model} from Hugging Face")
        AutoTokenizer.from_pretrained(model)
        AutoModelForCausalLM.from_pretrained(model)

