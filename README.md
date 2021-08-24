# Overview

This script produces a local drain direction (LDD) map based on 90-m MERIT Hydro data for a particular regions at a particular resolution. The script is entirely self-containing and only requires one to specify the path of the clone map and several output folders.

The script:
1. downloads and extracts the 90-m MERIT Hydro upstream area data;
1. resamples the upstream area data using a maximum filter (to retain the river network);
1. uses the inverted resampled upstream area data as elevation; and
1. computes the LDD.

# Instructions

1. Install the cross-platform wget and tar utilities to download and extract the MERIT Hydro data.
1. Clone the repository:
```
git clone https://github.com/hylken/create_ldd_from_merit
```
1. Modify`config.cfg` with the correct paths and folders. Create and activate a conda environment and run the script as follows:
```
cd create_ldd_from_merit
conda create --name <env> --file requirements.txt
conda activate <env>
python create_ldd_from_merit.py
```

