#!/bin/bash
#SBATCH --job-name=cruilla_video
#SBATCH --output=video_%j.log
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4         # 4-6 cores es el dulce para FFmpeg; más de 8 pierde eficiencia
#SBATCH --mem=8G                  # Suficiente memoria para retener los frames en RAM
#SBATCH --gres=gpu:1              # ¡CRUCIAL! Solicita 1 GPU NVIDIA para usar NVENC
#SBATCH --partition=interactive   # O la partición rápida/fina que use tu clúster

# Forzar rutas de CUDA en la sesión local de la VM
export PATH=/usr/local/cuda/bin:$PATH
export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH

# Activar entorno y correr script
source ~/miniconda3/etc/profile.d/conda.sh
conda activate dl

python3 newvideo.py