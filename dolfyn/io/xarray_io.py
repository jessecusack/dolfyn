import numpy as np
import xarray as xr
from ..data.time import num2date

def check_coords(dat):
    # reference frames particular to instrument
    # make sure assigned dataarray coordinates match what DOLfYN is reading in
    make = dat.inst_make
    model = dat.inst_model
    coord_sys = dat.coord_sys
    
    XYZ = ['X','Y','Z']
    ENU = ['E','N','U']
    beam = list(range(1,dat.vel.shape[0]+1))
    
    if 'Nortek' in make:
        if 'Sig' in model or '2' in model:
            inst = ['X','Y','Z1','Z2']
            earth = ['E','N','U1','U2']
            orient = {'beam':beam, 'inst':inst, 'earth':earth}
        else:
            inst = XYZ
            earth = ENU
            princ = ['streamwise','cross-stream','vertical']
            orient = {'beam':beam, 'inst':inst, 'earth':earth, 'princ':princ}
    elif 'RDI' in make:
        inst = ['X','Y','Z','err']
        earth = ['E','N','U','err']
        orient = {'beam':beam, 'ship':inst, 'inst':inst, 'earth':earth}
    
    orientIMU = {'beam':XYZ, 'inst':XYZ, 'ship':XYZ, 'earth':ENU,
                 'princ':['streamwise','cross-stream','vertical']}
    
    return orient[coord_sys], orientIMU[coord_sys]


def convert_xarray(dat):
    """
    Function that converts a DOLfYN data object into an xarray Dataset
    
    Inputs: dat = DOLfYN data object
            instrument = 'nortek' for a Nortek AWAC or Vector
                         'signature' for a Nortek Signature AD2CP
                         'trdi' for a Teledyne RDI ADCP
    Outputs: xarray Dataset
    """
    xdat = xr.Dataset()
    time = num2date(dat.mpltime)
    beam = list(range(1,dat.vel.shape[0]+1))
    
    # Every dataset has velocity, range, mpltime
    try: #ADCPs
        xdat['vel'] = xr.DataArray(dat['vel'],
                                   coords={'orient':beam,'range':dat['range'],'time':time},
                                   dims=['orient','range','time'],
                                   attrs={'units':'m/s',
                                          'description':'velocity'})
        xdat.orient.attrs['frame of reference'] = 'beam'
        xdat.range.attrs['units'] = 'm'
    except: #ADVs
        xdat['vel'] = xr.DataArray(dat['vel'],
                                   coords={'orient':beam,'time':time},
                                   dims=['orient','time'],
                                   attrs={'units':'m/s',
                                          'description':'velocity'})
        xdat.orient.attrs['frame of reference'] = 'inst'
    
    # Check for 5th beam, echosounder, or bottom track data (nortek & rdi)
    dtype = ['vel_b5','echo', 'vel_bt','dist_bt', 'bt_vel','bt_range']
    other = ['config','props']#,'sys']
    for key in dat:
        # check for 5th beam, echosounder, bottom track data
        # check size, dimensions
        size = np.shape(dat[key])
    
        if any(val in key for val in dtype):
            if 'b5' in key:
                xdat['vel_b5'] = xr.DataArray(dat['vel_b5'][0],
                                              coords={'range':dat['range_b5'],'time':time},
                                              dims=['range','time'],
                                              attrs={'units':'m/s',
                                                     'description':'5th beam velocity'})
                dtype.pop(dtype.index('vel_b5'))
                
            elif 'echo' in key:
                xdat['echo'] = xr.DataArray(dat['echo'],
                                            coords={'range_echo':dat['range_echo'],'time':time},
                                            dims=['range_echo','time'],
                                            attrs={'units':'dB',
                                                   'description':'echosounder return amplitude'})
                xdat.range_echo.attrs['units'] = 'm'
                dtype.pop(dtype.index('echo'))
                
            elif 'bt' in key:
                
                dtype.pop(dtype.index(key))
                if 'vel' in key:
                    xdat[key] = xr.DataArray(dat[key], 
                                             coords = {'orient':beam,'time':time},
                                             dims = ['orient','time'],
                                             attrs = {'units':'m/s',
                                             'description':'velocity measured by bottom track'})         

                elif ('range' in key) or ('dist' in key):
                    xdat[key] = xr.DataArray(dat[key], 
                                             coords = {'beam':beam,'time':time},
                                             dims = ['beam','time'],
                                             attrs = {'units':'m',
                                             'description':'depth to seafloor measured by bottom track'})                    
        
        elif 'depth' in key: # only for TRDI, converts pressure sensor?
            xdat['depth'] = xr.DataArray(dat['depth_m'],
                                         coords={'time':time},
                                         dims=['time'],
                                         attrs={'units':'m',
                                                'description':'depth of instrument'})
        # the other dictionaries
        elif size==():
            subdat = dat[key]
            
            if key=='env':
                #subkeys = ['c_sound','temp','salinity','pressure']
                for subkey in subdat:
                    xdat[subkey] = xr.DataArray(dat.env[subkey],
                                                coords={'time':time},
                                                dims=['time'])
                    if 'c_sound' in subkey:
                        xdat[subkey].attrs['units'] = 'm/s'
                        xdat[subkey].attrs['description'] = 'speed of sound'
                    elif 'temp' in subkey:
                        xdat[subkey].attrs['units'] = 'deg C'
                    elif 'salinity' in subkey:
                        xdat[subkey].attrs['units'] = 'psu'  
                    elif 'pressure' in subkey:
                        xdat[subkey].attrs['units'] = 'dbar'
    
            elif key=='signal':
                subkeys = ['amp','corr','amp_b5','corr_b5',
                           'amp_bt','corr_bt',
                           'prcnt_gd','prcnt_gd_bt']
                for subkey in subdat:
                    
                    if (subkey=='amp' or subkey=='corr' or subkey=='prcnt_gd'):
                        try: # ADCPs
                            xdat[subkey] = xr.DataArray(dat.signal[subkey],
                                                        coords={'beam':beam, 
                                                                'range':dat['range'], 
                                                                'time':time},
                                                        dims=['beam','range','time'])
                        except: # ADVs
                            xdat[subkey] = xr.DataArray(dat.signal[subkey],
                                                        coords={'beam':beam, 
                                                                'time':time},
                                                        dims=['beam', 'time'])
                        subkeys.pop(subkeys.index(subkey))
                        if subkey=='amp':
                            xdat[subkey].attrs['units'] = 'dB or counts'
                            xdat[subkey].attrs['description'] = 'beam return amplitude'
                        elif subkey=='corr':
                            xdat[subkey].attrs['units'] = '% or counts'
                            xdat[subkey].attrs['description'] = 'beam correlation'
                        elif subkey=='prcnt_gd':
                            xdat[subkey].attrs['units'] = '%'
                        
                    elif 'b5' in subkey:
                        xdat[subkey] = xr.DataArray(dat.signal[subkey][0],
                                                    coords={'range':dat['range_b5'], 
                                                          'time':time},
                                                    dims=['range','time'])
                        subkeys.pop(subkeys.index(subkey))
                        if 'amp' in subkey:
                            xdat[subkey].attrs['units'] = 'dB'
                            xdat[subkey].attrs['description'] = '5th beam return amplitude'
                        elif 'corr' in subkey:
                            xdat[subkey].attrs['units'] = '%'
                            xdat[subkey].attrs['description'] = '5th beam correlation'
                    
                    elif 'bt' in subkey:
                        xdat[subkey] = xr.DataArray(dat.signal[subkey],
                                                    coords={'beam':beam, 
                                                            'time':time},
                                                    dims=['beam','time'])
                        subkeys.pop(subkeys.index(subkey))
                        if 'amp' in subkey:
                            xdat[subkey].attrs['units'] = 'dB or counts'
                            xdat[subkey].attrs['description'] = 'amplitude of bottom track return signal'
                        elif 'corr' in subkey:
                            xdat[subkey].attrs['units'] = '% or counts'
                            xdat[subkey].attrs['description'] = 'correlation of bottom track return signal'
                        elif 'prcnt_gd' in subkey:
                            xdat[subkey].attrs['units'] = '%'
                            
            elif key=='orient':
                subkeys = ['accel','angrt','mag','orientmat','raw','longitude','latitude']
                for subkey in subdat:
                    if 'orientmat' in subkey:
                        xdat[subkey] = xr.DataArray(dat.orient[subkey],
                                                    coords={'inst':['X','Y','Z'], 
                                                            'earth':['E','N','U'], 
                                                            'time':time},
                                                    dims=['inst', 'earth', 'time'], 
                                                    attrs={'description':'orientation matrix for rotating data through coordinate frames'})
                    elif 'raw' in subkey:
                        for ky in ['heading', 'pitch', 'roll']:
                            xdat[ky] = xr.DataArray(dat['orient.raw'][ky],
                                                    coords={'time': time},
                                                    dims=['time'], 
                                                    attrs={'units': 'deg'}) 
                    elif len(np.shape(dat.orient[subkey]))==2:
                        try:
                            xdat[subkey] = xr.DataArray(dat.orient[subkey],
                                                        coords={'orientIMU':['X','Y','Z'], 
                                                                'time': time},
                                                        dims=['orientIMU', 'time'])
                        except:
                            xdat[subkey] = xr.DataArray(dat.orient[subkey],
                                                        coords={'quat':['q1','q2','q3','q4'], 
                                                                'time':time},
                                                        dims=['quat','time'])                           
                        if 'accel' in subkey:
                            xdat[subkey].attrs['units'] =  'm^2/s'
                            xdat[subkey].attrs['description'] = '3-axis accelerometer data'
                        elif 'angrt' in subkey:
                            xdat[subkey].attrs['units'] =  'rad/s'
                            xdat[subkey].attrs['description'] = 'angular rotation rate'     
                        elif 'mag' in subkey:
                            xdat[subkey].attrs['units'] =  'milligauss or gauss'
                            xdat[subkey].attrs['description'] = '3-axis magnetometer data'
                        elif 'quaternion' in subkey:
                            xdat[subkey].attrs['description'] = 'unit quaternions'
                            
                    elif ('lon' in subkey) or ('lat' in subkey):
                        xdat[subkey] = xr.DataArray(dat.orient[subkey],
                                                    dims=['time'], 
                                                    coords={'time': time},
                                                    attrs={'units': 'degrees'},)
    
            # all the other stuff goes into attributes
            # need to change datatype to be netcdf "compatible" in order to save
            elif any(val in key for val in other):
                for subkey in dat[key]:
                    subsize = np.shape(dat[key][subkey])
                    if type(dat[key][subkey])==dict:
                        #pass # no good way to make the config files savable to netcdf
                        xdat.attrs[subkey] = [[str(x)] for x in dat[key][subkey].items()]
                    elif type(dat[key][subkey])==set:
                        xdat.attrs[subkey] = list(dat[key][subkey])
                    elif type(dat[key][subkey])==np.ndarray:
                        if len(subsize)==1 and subsize[0]>1:
                            #xdat[subkey] = xr.DataArray(dat[key][subkey],
                            #                            coords={'time':time},
                            #                            dims='time')
                            xdat.attrs[subkey] = dat[key][subkey]
                        else:
                            xdat[subkey] = xr.DataArray(dat[key][subkey])
                    elif 'alt' in subkey:
                        pass # because I'm not sure what to do with this at the moment
                    else:
                        xdat.attrs[subkey] = dat[key][subkey]
    
    # Set dataset coordinate attributes             
    if 'range' in xdat:
        xdat.range.attrs['units'] = 'm'
    
    # apply current reference frame to rotated variables
    # 4-axis velocity terms vs 3-axis IMU data?
    current_FoR, IMU_FoR = check_coords(xdat)
    xdat = xdat.assign_coords({'orient':current_FoR})
    xdat = xdat.assign_coords({'orientIMU':IMU_FoR})
    
    return xdat


def save_xr(fname, dat):
    dat.to_netcdf(fname + '.nc', format='NETCDF4', engine='h5netcdf', invalid_netcdf=True)
    

def load_xr(fname):
    return xr.load_dataset(fname + '.nc')
    