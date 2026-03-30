#!/bin/bash
#SBATCH -n 4 # Number of cores
#SBATCH -N 1 # Ensure that all cores are on one machine
#SBATCH -D ./tmp # working directory
#SBATCH -t 0-00:30 # Runtime in D-HH:MM
#SBATCH -p dcca40 # Partition to submit to
#SBATCH --mem 12288 # Requested 12GB of memory.
#SBATCH -o %x_%u_%j.out # File to which STDOUT will be written
#SBATCH -e %x_%u_%j.err # File to which STDERR will be written
#SBATCH --gres gpu:1 # Request 1 gpu

python3 /hhome/ps2g07/code/Festival-Cruilla/src/models/train_auraface.py