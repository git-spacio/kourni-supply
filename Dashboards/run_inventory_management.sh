#!/bin/bash
# Activate the conda environment
source /home/snparada/miniconda3/etc/profile.d/conda.sh
conda activate Spacio

# Navigate to the app directory
cd /home/snparada/Spacionatural/Supply/Dashboards

# Run the Streamlit app
streamlit run inventory_management.py --server.port=8502 --server.address=127.0.0.1
