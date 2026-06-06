#!/bin/bash
#SBATCH -n 4 # Number of cores
#SBATCH -N 1 # Ensure that all cores are on one machine
#SBATCH -D ./tmp # working directory
#SBATCH -t 0-00:30 # Runtime in D-HH:MM
#SBATCH -p dcca40 # Partition to submit to
#SBATCH --mem 12288 # Requested 12GB of memory.
#SBATCH -o %x_%u_%j.out # File to which STDOUT will be written
#SBATCH -e %x_%u_%j.err # File to which STDERR will be written
#SBATCH --gres=gpu:1 # Request 1 gpu

#module load cuda/11.8   

source ~/miniconda3/etc/profile.d/conda.sh

export LD_LIBRARY_PATH=$CONDA_PREFIX/lib:$LD_LIBRARY_PATH


conda activate sp_env

#which python
#python -c "import torch, transformers; print('torch=', torch.__version__); print('transformers=', transformers.__version__); print('file=', transformers.__file__); print('cuda=', torch.cuda.is_available())"
#python -c "from transformers.configuration_utils import layer_type_validation; print('layer_type_validation OK')"
#python -c "import einops, vector_quantize_pytorch; print('ok')"

#python3 /hhome/ps2g07/code/Festival-Cruilla/face2label/models/train_auraface.py
#python3 /hhome/ps2g07/code/Festival-Cruilla/models/ACE-Step-1.5/generate.py
python3 /hhome/ps2g07/code/Festival-Cruilla/main.py \
  --image "/export/hhome/ps2g07/code/Festival-Cruilla/inputs/cruilla_guy.png" \
  --mood sad \
  --instrument guitar \
  --era actual \ 
  --with-music