#!/usr/bin/env python  
# -*- coding: utf-8 -*-

__author__ = "Hylke E. Beck"
__email__ = "hylke.beck@gmail.com"
__date__ = "August 2021"

import os, sys, glob, time, pdb
import pandas as pd
import numpy as np
import pcraster as pcr
from netCDF4 import Dataset
import matplotlib.pyplot as plt
import subprocess
import rasterio
from scipy.ndimage import gaussian_filter

def latlon2rowcol(lat,lon,res,lat_upper,lon_left):
    row = np.round((lat_upper-lat)/res-0.5).astype(int)
    col = np.round((lon-lon_left)/res-0.5).astype(int)    
    return row.squeeze(),col.squeeze()

def rowcol2latlon(row,col,res,lat_upper,lon_left):
    lat = lat_upper-row*res-res/2
    lon = lon_left+col*res+res/2
    return lat.squeeze(),lon.squeeze()
    
def imresize_max(oldarray,newshape):
    # Resize array using max filter. Inefficient, but works.
    
    # Determine resize factor
    oldshape = oldarray.shape
    factor = oldshape[0]/newshape[0]    
    if factor!=np.round(factor): 
        raise ValueError('Resize factor of '+str(factor)+' not integer, needs to be integer')    
    factor = factor.astype(int)
    
    # Loop over new grid and compute max
    newarray = np.zeros(newshape,dtype=np.single)*np.NaN
    for ii in np.arange(newshape[0]):
        for jj in np.arange(newshape[1]):
            newarray[ii,jj] = np.nanmax(oldarray[ii*factor:(ii+1)*factor,jj*factor:(jj+1)*factor])
    
    return newarray

def save_netcdf(file, varname, data, lat, lon):

    if os.path.isfile(file)==True: 
        os.remove(file)

    ncfile = Dataset(file, 'w', format='NETCDF4')

    ncfile.createDimension('lon', len(lon))
    ncfile.createDimension('lat', len(lat))

    ncfile.createVariable('lon', 'f8', ('lon',))
    ncfile.variables['lon'][:] = lon
    ncfile.variables['lon'].units = 'degrees_east'
    ncfile.variables['lon'].long_name = 'longitude'

    ncfile.createVariable('lat', 'f8', ('lat',))
    ncfile.variables['lat'][:] = lat
    ncfile.variables['lat'].units = 'degrees_north'
    ncfile.variables['lat'].long_name = 'latitude'
    
    ncfile.createVariable(varname, data.dtype, ('lat', 'lon'), zlib=True, chunksizes=(32,32,), fill_value=-9999)

    ncfile.variables[varname][:,:] = data
    
    ncfile.close()
    
def load_config(filepath):
    '''Load configuration file into dict'''
    
    df = pd.read_csv(filepath,header=None,index_col=False)
    config = {}
    for ii in np.arange(len(df)): 
        string = df.iloc[ii,0].replace(" ","")
        varname = string.rpartition('=')[0]
        varcontents = string.rpartition('=')[2]
        try:
            varcontents = float(varcontents)
        except:
            pass
        config[varname] = varcontents
    return config
    
# Load configuration file
config = load_config('config.cfg')

# Load MERIT Hydro credentials
merit_user_pw = pd.read_csv('merit_user_pw.txt',index_col=None,header=None)
merit_user = merit_user_pw.iloc[0][0]
merit_pw = merit_user_pw.iloc[1][0]

if os.path.isdir(config['merit_folder'])==False:
    os.mkdir(config['merit_folder'])

if os.path.isdir(config['output_folder'])==False:
    os.mkdir(config['output_folder'])


############################################################################
#   Download and untar all MERIT Hydro upstream data
############################################################################

url_pre = 'http://hydro.iis.u-tokyo.ac.jp/~yamadai/MERIT_Hydro/distribute/v1.0/'

lats = ['n60','n30','n00','s30','s60']
lons = ['w180','w150','w120','w090','w060','w030','e000','e030','e060','e090','e120','e150']
for lat in lats:
    for lon in lons:
        if os.path.isdir(os.path.join(config['merit_folder'],'upa_'+lat+lon)): continue
        filename = 'upa_'+lat+lon+'.tar'
        command = 'wget '+url_pre+filename+' --no-clobber --user='+merit_user+' --password='+merit_pw+' --directory-prefix='+config['merit_folder']
        subprocess.call(command,shell=True)
        command = 'tar -xvf '+os.path.join(config['merit_folder'],filename)+' -C '+config['merit_folder']
        subprocess.call(command,shell=True)
        if os.path.isfile(os.path.join(config['merit_folder'],filename)):
            os.remove(os.path.join(config['merit_folder'],filename))


############################################################################
#   Make global upstream map at specified resolution based on MERIT Hydro 
#   upstream data
############################################################################

if os.path.isfile(os.path.join(config['output_folder'],'upstream_area_global.npy'))==False:

    global_shape = (int(180/config['res']),int(360/config['res']))
    upstream_area_global = np.zeros(global_shape)*np.NaN
    
    for subdir, dirs, files in os.walk(config['merit_folder']):
        for file in files:        
            
            print('--------------------------------------------------------------------------------')
            print('Processing '+file)
            t1 = time.time()
            
            # Resize using maximum filter
            oldarray = rasterio.open(os.path.join(subdir, file)).read(1)
            oldarray[oldarray<0] = 9999999 # Necessary to ensure that all rivers flow into the ocean
            factor = config['res']/(5/6000)
            factor = np.round(factor*1000000000000)/1000000000000
            if factor!=np.round(factor): 
                raise ValueError('Resize factor of '+str(factor)+' not integer, needs to be integer')
            factor = factor.astype(int)
            newshape = (oldarray.shape[0]//factor,oldarray.shape[1]//factor)
            newarray = imresize_max(oldarray,newshape)
            
            # Insert into global map
            tile_lat_bottom = float(file[:3].replace("n","").replace("s","-"))
            tile_lon_left = float(file[3:7].replace("e","").replace("w","-"))
            tile_row_bottom, tile_col_left = latlon2rowcol(tile_lat_bottom+config['res']/2,tile_lon_left+config['res']/2,config['res'],90,-180)
            upstream_area_global[tile_row_bottom-newshape[0]+1:tile_row_bottom+1,tile_col_left:tile_col_left+newshape[1]] = newarray
            
            print('Time elapsed is ' + str(time.time() - t1) + ' sec')

    with open(os.path.join(config['output_folder'],'upstream_area_global.npy'), 'wb') as f:
        np.save(f, upstream_area_global)

# Load resampled global upstream area map from disk
with open(os.path.join(config['output_folder'],'upstream_area_global.npy'), 'rb') as f:
    upstream_area_global = np.load(f)

    
############################################################################
#   Create ldd based on global upstream area map
############################################################################

# Load clone map
dset = Dataset(config['clonemap_path'])
clone_lat = dset.variables['lat'][:]
clone_lon = dset.variables['lon'][:]
clone_res = clone_lon[1]-clone_lon[0]
varname = list(dset.variables.keys())[-1]
clone_np = np.array(dset.variables[varname][:])
pcr.setclone(clone_np.shape[0],clone_np.shape[1],clone_res,clone_lon[0]-clone_res/2,clone_lat[0]-clone_res/2)

# Create grid-cell area map
xi, yi = np.meshgrid(clone_lon, clone_lat)
area_np = (40075*config['res']/360)**2*np.cos(np.deg2rad(yi))
area_pcr = pcr.numpy2pcr(pcr.Scalar,area_np,mv=-9999)

# Subset global upstream map to clone map region
if np.round(clone_res*1000000)!=np.round(config['res']*1000000):
    raise ValueError('Clone resolution of '+str(clone_res)+' does not match target resolution of '+str(config['res']))
row_upper,col_left = latlon2rowcol(clone_lat[0],clone_lon[0],config['res'],90,-180)
upstream_area = upstream_area_global[row_upper:row_upper+len(clone_lat),col_left:col_left+len(clone_lon)]
upstream_area[np.isnan(upstream_area)] = np.nanmax(upstream_area_global)

# Produce ldd by inverting upstream map
# To make sure rivers flow away from continents, we introduce a gradient near shores
fake_elev_np = 9999999-upstream_area
nearshore_gradient = gaussian_filter(np.single(fake_elev_np!=0)*100,sigma=25)
nearshore_gradient[fake_elev_np!=0] = np.NaN
nearshore_gradient = nearshore_gradient-np.nanmax(nearshore_gradient)
fake_elev_np[fake_elev_np==0] = nearshore_gradient[fake_elev_np==0]
fake_elev_pcr = pcr.numpy2pcr(pcr.Scalar,fake_elev_np,mv=9999999)
ldd_pcr = pcr.lddcreate(fake_elev_pcr,0,0,0,0)
ldd_np = pcr.pcr2numpy(ldd_pcr,mv=-9999)
upstreamarea_pcr = pcr.accuflux(ldd_pcr,area_pcr)
upstreamarea_np = pcr.pcr2numpy(upstreamarea_pcr,mv=9999999)

# Save results
save_netcdf(os.path.join(config['output_folder'],'ldd.nc'), 'ldd', ldd_np, clone_lat, clone_lon)
save_netcdf(os.path.join(config['output_folder'],'ups.nc'), 'ups', upstreamarea_np, clone_lat, clone_lon)


############################################################################
#   Plot some maps
############################################################################

plt.figure(1)
plt.imshow(np.log10(upstreamarea_np),vmin=0,vmax=6)
plt.title('New upstream area (upstreamarea_np)')

plt.figure(2)
plt.imshow(np.log10(upstream_area_global),vmin=0,vmax=6)
plt.title('MERIT Hydro upstream area (upstream_area_global)')

plt.show(block=False)

pdb.set_trace()