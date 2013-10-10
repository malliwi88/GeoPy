'''
Created on 2013-09-28

This module contains meta data and access functions for WRF model output. 

@author: Andre R. Erler, GPL v3
'''

# external imports
import numpy as np
import netCDF4 as nc
import collections as col
import os
# from atmdyn.properties import variablePlotatts
from geodata.base import Axis
from geodata.netcdf import DatasetNetCDF, VarNC
from geodata.gdal import addGDALtoDataset, getProjFromDict, GridDefinition
from geodata.misc import DatasetError, isInt, AxisError
from datasets.common import translateVarNames, days_per_month, name_of_month, data_root
from geodata.process import CentralProcessingUnit


## get WRF projection and grid definition 
# N.B.: Unlike with observational datasets, model Meta-data depends on the experiment and has to be 
#       loaded from the NetCFD-file; a few conventions have to be defied, however.

# get projection NetCDF attributes
def getWRFproj(dataset, name=''):
  ''' Method to infer projection parameters from a WRF output file and return a GDAL SpatialReference object. '''
  if not isinstance(dataset,nc.Dataset): raise TypeError
  if not isinstance(name,basestring): raise TypeError
  if dataset.MAP_PROJ == 1: 
    # Lambert Conformal Conic projection parameters
    proj = 'lcc' # Lambert Conformal Conic  
    lat_1 = dataset.TRUELAT1 # Latitude of first standard parallel
    lat_2 = dataset.TRUELAT2 # Latitude of second standard parallel
    lat_0 = dataset.CEN_LAT # Latitude of natural origin
    lon_0 = dataset.CEN_LON # Longitude of natural origin
    #if dataset.CEN_LON != dataset.STAND_LON: raise GDALError  
  else:
    raise NotImplementedError, "Can only infer projection parameters for Lambert Conformal Conic projection (#1)."
  projdict = dict(proj=proj,lat_1=lat_1,lat_2=lat_2,lat_0=lat_0,lon_0=lon_0)
  # pass results to GDAL module to get projection object
  return getProjFromDict(projdict, name=name, GeoCS='WGS84', convention='Proj4')  

# infer grid (projection and axes) from constants file
def getWRFgrid(name=None, experiment=None, domains=None, folder=None, filename='wrfconst_d{0:0=2d}.nc', ncformat='NETCDF4'):
  ''' Infer the WRF grid configuration from an output file and return a GridDefinition object. '''
  # check input
  folder, names, domains = getFolderNameDomain(name=name, experiment=experiment, domains=domains, folder=folder)
  if isinstance(filename,basestring): filepath = '{}/{}'.format(folder,filename) # still contains formaters
  else: raise TypeError
  maxdom = max(domains)
  # files to work with
  for n in xrange(1,maxdom+1):
    dnfile = filepath.format(n)
    if not os.path.exists(dnfile):
      if n in domains: raise IOError, 'File {} for domain {:d} not found!'.format(dnfile,domains)
      else: raise IOError, 'File {} for domain {:d} not found; this file is necessary to infer the geotransform for other domains.'.format(dnfile)
  # open first domain file (special treatment)
  dn = nc.Dataset(filepath.format(1), mode='r', format=ncformat)
  name=experiment if isinstance(experiment,basestring) else name[0] # omit domain information, which is irrelevant
  projection = getWRFproj(dn, name=name) # same for all
  # infer size and geotransform
  def getXYlen(ds):
    ''' a short function to infer the length of horizontal axes from a dataset with unknown naming conventions ''' 
    if 'west_east' in ds.dimensions and 'south_north' in ds.dimensions:
      nx = len(ds.dimensions['west_east']); ny = len(ds.dimensions['south_north'])
    elif 'x' in ds.dimensions and 'y' in ds.dimensions:
      nx = len(ds.dimensions['x']); ny = len(ds.dimensions['y'])
    else: raise AxisError, 'No horizontal axis found, necessary to infer projection/grid configuration.'
    return nx,ny
  dx = dn.DX; dy = dn.DY
  nx,ny = getXYlen(dn)
  x0 = nx*dx/2; y0 = ny*dy/2 
  size = (nx, ny); geotransform = (x0,dx,0.,y0,0.,dy)
  name = names[0] if 1 in domains else 'tmp'  # update name, if first domain has a name...
  griddef = GridDefinition(name=name, projection=projection, geotransform=geotransform, size=size)
  dn.close()
  if 1 in domains: griddefs = [griddef]
  else: griddefs = []
  if maxdom > 1:
    # now infer grid of domain of interest
    geotransforms = [geotransform]
    # loop over grids
    for n in xrange(2,maxdom+1):
      # open file
      dn = nc.Dataset(filepath.format(n), mode='r', format=ncformat)
      if not n == dn.GRID_ID: raise DatasetError # just a check
      pid = dn.PARENT_ID-1 # parent grid ID
      # infer size and geotransform      
      px0,pdx,s,py0,t,pdy = geotransforms[pid]      
      x0 = px0+dn.I_PARENT_START*pdx; y0 = py0+dn.J_PARENT_START*pdy
      size = getXYlen(dn) 
      geotransform = (x0,dn.DX,0.,y0,0.,dn.DY)
      dn.close()
      geotransforms.append(geotransform) # we need that to construct the next nested domain
      if n in domains:
        name = names[len(griddefs)] # current index = current length - 1  =>  next index = current length
        griddefs.append(GridDefinition(name=name, projection=projection, geotransform=geotransform, size=size))
  # return a GridDefinition object
  return tuple(griddefs)  

# return name and folder
def getFolderNameDomain(name=None, experiment=None, domains=None, folder=None):
  ''' Convenience function to infer type-check the name and folder of an experiment based on various input. '''
  # check domains
  if isinstance(domains,col.Iterable):
    if not all(isInt(domains)): raise TypeError
    if not isinstance(domains,list): domains = list(domains)
    if not domains == sorted(domains): raise IndexError, 'Domains have to sorted in ascending order.'
  elif isInt(domains): domains = [domains]
  else: raise TypeError  
  # figure out experiment name
  if experiment is None:
    if not isinstance(folder,basestring): 
      raise IOError, "Need to specify an experiment folder in order to load data."
    if isinstance(name,col.Iterable) and all([isinstance(n,basestring) for n in name]): names = name
    elif isinstance(name,basestring): names = [name]
    else: raise DatasetError, "Need to specify an experiment name in order to load data."
  else:
    # root folder
    if not isinstance(experiment,basestring): raise TypeError
    if folder is None: folder = '{}/{}/'.format(root_folder,experiment)
    elif not isinstance(folder,basestring): raise TypeError
    # expand name
    if name is None: name = '{}'.format(experiment)
    if isinstance(name,basestring): 
      names = ['{0:s}_d{1:0=2d}'.format(name,domain) for domain in domains]
    elif isinstance(name,col.Iterable):
      if len(domains) != len(name): raise DatasetError  
      names = name 
    else: raise TypeError      
  # check if folder exists
  if not os.path.exists(folder): raise IOError
  # return name and folder
  return folder, tuple(names), tuple(domains)
  

## variable attributes and name
class FileType(object): pass # ''' Container class for all attributes of of the constants files. '''
# constants
class Const(FileType):
  ''' Variables and attributes of the constants files. '''
  def __init__(self):
    self.atts = dict(HGT    = dict(name='zs', units='m'), # surface elevation
                     XLONG  = dict(name='lon2D', units='deg E'), # geographic longitude field
                     XLAT   = dict(name='lat2D', units='deg N')) # geographic latitude field
    self.vars = self.atts.keys()    
    self.climfile = 'wrfconst_d{0:0=2d}(1:s}.nc' # the filename needs to be extended by (domain,'_'+grid)
    self.tsfile = 'wrfconst_d{0:0=2d}.nc' # the filename needs to be extended by (domain,)
# surface variables
class Srfc(FileType):
  ''' Variables and attributes of the surface files. '''
  def __init__(self):
    self.atts = dict(T2     = dict(name='T2', units='K'), # 2m Temperature
                     Q2     = dict(name='Q2', units='Pa'), # 2m water vapor pressure
                     RAIN   = dict(name='precip', units='kg/m^2/s'), # total precipitation rate (kg/m^2/s)
                     RAINC  = dict(name='preccu', units='kg/m^2/s'), # convective precipitation rate (kg/m^2/s)
                     RAINNC = dict(name='precnc', units='kg/m^2/s'), # grid-scale precipitation rate (kg/m^2/s)
                     SNOW   = dict(name='snow', units='kg/m^2'), # snow water equivalent
                     SNOWH  = dict(name='snowh', units='m'), # snow depth
                     PSFC   = dict(name='ps', units='Pa')) # surface pressure
    self.vars = self.atts.keys()    
    self.climfile = 'wrfsrfc_d{0:0=2d}{1:s}_clim{2:s}.nc' # the filename needs to be extended by (domain,'_'+grid,'_'+period)
    self.tsfile = 'wrfsrfc_d{0:0=2d}_monthly.nc' # the filename needs to be extended by (domain,)
# hydro variables
class Hydro(FileType):
  ''' Variables and attributes of the hydrological files. '''
  def __init__(self):
    self.atts = dict(T2     = dict(name='T2', units='K'), # daily mean 2m Temperature
                     RAIN   = dict(name='precip', units='kg/m^2/s'), # total precipitation rate
                     RAINC  = dict(name='preccu', units='kg/m^2/s'), # convective precipitation rate
                     RAINNC = dict(name='precnc', units='kg/m^2/s'), # grid-scale precipitation rate
                     SFCEVP = dict(name='evap', units='kg/m^2/s'), # actual surface evaporation/ET rate
                     ACSNOM = dict(name='snwmlt', units='kg/m^2/s'), # snow melting rate 
                     POTEVP = dict(name='pet', units='kg/m^2/s')) # potential evapo-transpiration rate
    self.vars = self.atts.keys()    
    self.climfile = 'wrfhydro_d{0:0=2d}{1:s}_clim{2:s}.nc' # the filename needs to be extended by (domain,'_'+grid,'_'+period)
    self.tsfile = 'wrfhydro_d{0:0=2d}_monthly.nc' # the filename needs to be extended by (domain,)
# extreme value variables
class Xtrm(FileType):
  ''' Variables and attributes of the extreme value files. '''
  def __init__(self):
    self.atts = dict(T2MEAN = dict(name='Tmean', units='K'),  # daily mean Temperature (at 2m)
                     T2MIN  = dict(name='Tmin', units='K'),   # daily minimum Temperature (at 2m)
                     T2MAX  = dict(name='Tmax', units='K'),   # daily maximum Temperature (at 2m)
                     T2STD  = dict(name='Tstd', units='K'),   # daily Temperature standard deviation (at 2m)
                     SKINTEMPMEAN = dict(name='TSmean', units='K'),  # daily mean Skin Temperature
                     SKINTEMPMIN  = dict(name='TSmin', units='K'),   # daily minimum Skin Temperature
                     SKINTEMPMAX  = dict(name='TSmax', units='K'),   # daily maximum Skin Temperature
                     SKINTEMPSTD  = dict(name='TSstd', units='K'),   # daily Skin Temperature standard deviation                     
                     Q2MEAN = dict(name='Qmean', units='Pa'), # daily mean Water Vapor Pressure (at 2m)
                     Q2MIN  = dict(name='Qmin', units='Pa'),  # daily minimum Water Vapor Pressure (at 2m)
                     Q2MAX  = dict(name='Qmax', units='Pa'),  # daily maximum Water Vapor Pressure (at 2m)
                     Q2STD  = dict(name='Qstd', units='Pa'),  # daily Water Vapor Pressure standard deviation (at 2m)
                     SPDUV10MEAN = dict(name='U10mean', units='m/s'), # daily mean Wind Speed (at 10m)
                     SPDUV10MAX  = dict(name='U10max', units='m/s'),  # daily maximum Wind Speed (at 10m)
                     SPDUV10STD  = dict(name='U10std', units='m/s'),  # daily Wind Speed standard deviation (at 10m)
                     U10MEAN = dict(name='u10mean', units='m/s'), # daily mean Westerly Wind (at 10m)
                     V10MEAN = dict(name='v10mean', units='m/s'), # daily mean Southerly Wind (at 10m)                     
                     RAINCVMEAN  = dict(name='preccumean', units='kg/m^2/s'), # daily mean convective precipitation rate
                     RAINCVMAX  = dict(name='preccumax', units='kg/m^2/s'), # daily maximum convective precipitation rate
                     RAINCVSTD  = dict(name='preccustd', units='kg/m^2/s'), # daily convective precip standard deviation
                     RAINNCVMEAN = dict(name='precncmean', units='kg/m^2/s'), # daily mean grid-scale precipitation rate
                     RAINNCVMAX  = dict(name='precncmax', units='kg/m^2/s'), # daily maximum grid-scale precipitation rate
                     RAINNCVSTD  = dict(name='precncstd', units='kg/m^2/s')) # daily grid-scale precip standard deviation                     
    self.vars = self.atts.keys()    
    self.climfile = 'wrfxtrm_d{0:0=2d}{1:s}_clim{2:s}.nc' # the filename needs to be extended by (domain,'_'+grid,'_'+period)
    self.tsfile = 'wrfxtrm_d{0:0=2d}_monthly.nc' # the filename needs to be extended by (domain,)
# variables on selected pressure levels: 850 hPa, 700 hPa, 500 hPa, 250 hPa, 100 hPa
class Plev3D(FileType):
  ''' Variables and attributes of the pressure level files. '''
  def __init__(self):
    self.atts = dict(T_PL     = dict(name='T', units='K', fillValue=-999),   # Temperature
                     TD_PL    = dict(name='Td', units='K', fillValue=-999),  # Dew-point Temperature
                     RH_PL    = dict(name='RH', units='', fillValue=-999),   # Relative Humidity
                     GHT_PL   = dict(name='Z', units='m', fillValue=-999),   # Geopotential Height 
                     S_PL     = dict(name='U', units='m/s', fillValue=-999), # Wind Speed
                     U_PL     = dict(name='u', units='m/s', fillValue=-999), # Zonal Wind Speed
                     V_PL     = dict(name='v', units='m/s', fillValue=-999)) # Meridional Wind Speed
#                      P_PL     = dict(name='p', units='Pa'))  # Pressure
    self.vars = self.atts.keys()    
    self.climfile = 'wrfplev3d_d{0:0=2d}{1:s}_clim{2:s}.nc' # the filename needs to be extended by (domain,'_'+grid,'_'+period)
    self.tsfile = 'wrfplev3d_d{0:0=2d}_monthly.nc' # the filename needs to be extended by (domain,)

# axes (don't have their own file)
class Axes(FileType):
  ''' A mock-filetype for axes. '''
  def __init__(self):
    self.atts = dict(Time        = dict(name='time', units='month'), # time coordinate
                     time        = dict(name='time', units='month'), # time coordinate
                     # N.B.: the time coordinate is only used for the monthly time-series data, not the LTM
                     #       the time offset is chose such that 1979 begins with the origin (time=0)
                     west_east   = dict(name='x', units='m'), # projected west-east coordinate
                     south_north = dict(name='y', units='m'), # projected south-north coordinate
                     x           = dict(name='x', units='m'), # projected west-east coordinate
                     y           = dict(name='y', units='m'), # projected south-north coordinate
                     num_press_levels_stag = dict(name='p', units='Pa')) # pressure coordinate
    self.vars = self.atts.keys()
    self.climfile = None
    self.tsfile = None

# data source/location
fileclasses = dict(const=Const(), srfc=Srfc(), xtrm=Xtrm(), plev3d=Plev3D(), hydro=Hydro(), axes=Axes())
root_folder = data_root + 'WRF/Downscaling/' # long-term mean folder


## Functions to load different types of WRF datasets

# Time-Series (monthly)
def loadWRF_TS(experiment=None, name=None, domains=2, filetypes=None, varlist=None, varatts=None):
  ''' Get a properly formatted WRF dataset with monthly time-series. '''
  # prepare input  
  ltuple = isinstance(domains,col.Iterable)
  folder, names, domains = getFolderNameDomain(name=name, experiment=experiment, domains=domains, folder=None)
  # generate filelist and attributes based on filetypes and domain
  atts = dict(); filelist = [] 
  for filetype in filetypes + ['axes']:
    fileclass = fileclasses[filetype]
    if fileclass.tsfile is not None: filelist.append(fileclass.tsfile) 
    atts.update(fileclass.atts)  
  if varatts is not None: atts.update(varatts)
  # translate varlist
  if varlist is None: varlist = atts.keys()
  elif varatts: varlist = translateVarNames(varlist, varatts)
  # infer projection and grid and generate horizontal map axes
  # N.B.: unlike with other datasets, the projection has to be inferred from the netcdf files  
  if 'const' in filetypes: filename = fileclasses['const'].tsfile # constants files preferred...
  else: filename = fileclasses.values()[0].tsfile # just use the first filetype
  griddefs = getWRFgrid(name=names, experiment=None, domains=domains, folder=folder, filename=filename)
  assert len(griddefs) == len(domains)
  datasets = []
  for name,domain,griddef in zip(names,domains,griddefs):
    # domain-sensitive parameters
    axes = dict(west_east=griddef.xlon, south_north=griddef.ylat, x=griddef.xlon, y=griddef.ylat) # map axes
    filenames = [filename.format(domain) for filename in filelist] # insert domain number
    # load dataset
    dataset = DatasetNetCDF(name=name, folder=folder, filelist=filenames, varlist=varlist, varatts=atts, 
                            axes=axes, multifile=False, ncformat='NETCDF4', squeeze=True)
    # load pressure levels (doesn't work automatically, because variable and dimension have different names and dimensions)
    if dataset.hasAxis('p'): 
      dataset.axes['p'].updateCoord(dataset.dataset.variables['P_PL'][0,:])
    # add projection
    dataset = addGDALtoDataset(dataset, projection=griddef.projection, geotransform=griddef.geotransform)
    # safety checks
    assert dataset.axes['x'] == griddef.xlon
    assert dataset.axes['y'] == griddef.ylat   
    assert all([dataset.axes['x'] == var.getAxis('x') for var in dataset.variables.values() if var.hasAxis('x')])
    assert all([dataset.axes['y'] == var.getAxis('y') for var in dataset.variables.values() if var.hasAxis('y')])
    # append to list
    datasets.append(dataset) 
  # return formatted dataset
  if not ltuple: datasets = datasets[0]
  return datasets
  

# pre-processed climatology files (varatts etc. should not be necessary) 
# function to load these files...
def loadWRF(name=None, domain=None, period=None, grid=None, varlist=None, filetypes=None):
  ''' Get the pre-processed monthly NARR climatology as a DatasetNetCDF. '''
  avgfolder = data_root + name + '/' # long-term mean folder
  # prepare input
  if domain not in ('025','05', '10', '25'): raise DatasetError, "Selected resolution '%s' is not available!"%resolution
  # translate varlist
  if varlist and varatts: varlist = translateVarNames(varlist, varatts)
  # load variables separately
  if 'p' in varlist:
    dataset = DatasetNetCDF(name=name, folder=folder, filelist=['normals_v2011_%s.nc'%resolution], varlist=['p'], 
                            varatts=varatts, ncformat='NETCDF4_CLASSIC')
  if 's' in varlist: 
    gauges = nc.Dataset(folder+'normals_gauges_v2011_%s.nc'%resolution, mode='r', format='NETCDF4_CLASSIC')
    stations = Variable(data=gauges.variables['p'][0,:,:], axes=(dataset.lat,dataset.lon), **varatts['s'])
    # consolidate dataset
    dataset.addVariable(stations, asNC=False, copy=True)  
  dataset = addGDALtoDataset(dataset, projection=None, geotransform=None)
  # return formatted dataset
  return dataset


## (ab)use main execution for quick test
if __name__ == '__main__':
    
  
#   mode = 'test_climatology'
#   mode = 'test_timeseries'
  mode = 'average_timeseries'
  
  experiment = 'max-ctrl'
  domain = 1
  filetypes = ['srfc','xtrm','plev3d','hydro',]
  filetypes = ['plev3d','hydro',]
  grid = 'WRF'
  period = (1979,1981)

  
  # load averaged climatology file
  if mode == 'test_climatology':
    
    print('')
    dataset = loadWRF(period=period)
    print(dataset)
    print('')
    print(dataset.geotransform)
  
  
  # load monthly time-series file
  elif mode == 'test_timeseries':
    
    datasets = loadWRF_TS(experiment='max-ctrl', domains=(2,), filetypes=['srfc'])
    for dataset in datasets:
      print('')
      print(dataset)
      print('')
      print(dataset.geotransform)
    
                        
  # generate averaged climatology
  elif mode == 'average_timeseries':
    
    # determine coordinate arrays
    if grid != 'WRF':    
      if grid == '025': dlon = dlat = 0.25 # resolution
      elif grid == '05': dlon = dlat = 0.5
      elif grid == '10': dlon = dlat = 1.0
      elif grid == '25': dlon = dlat = 2.5 
      slon, slat, elon, elat = -179.75, 3.25, -69.75, 85.75
      assert (elon-slon) % dlon == 0 
      lon = np.linspace(slon+dlon/2,elon-dlon/2,(elon-slon)/dlon)
      assert (elat-slat) % dlat == 0
      lat = np.linspace(slat+dlat/2,elat-dlat/2,(elat-slat)/dlat)
      # add new geographic coordinate axes for projected map
      xlon = Axis(coord=lon, atts=dict(name='lon', long_name='longitude', units='deg E'))
      ylat = Axis(coord=lat, atts=dict(name='lat', long_name='latitude', units='deg N'))
    else:
      xlon = None; ylat = None
    
    # begin (loop over files)
    periodstr = '%4i-%4i'%period
    avgfolder = root_folder + experiment + '/'
    print('\n')
    print('   ***   Processing Grid %s from %s   ***   '%(grid,periodstr))
    
    for filetype in filetypes:    
      
      fileclass = fileclasses[filetype]
      
      # load source
      print('       Source: \'%s\'\n'%fileclass.tsfile.format(domain))
      source = loadWRF_TS(experiment=experiment, filetypes=[filetype])# comes out as a tuple...
      print(source)
      print('\n')
      # prepare sink
      gridstr = '' if grid is 'WRF' else '_'+grid
      filename = fileclass.climfile.format(domain,gridstr,'_'+periodstr)
      if os.path.exists(avgfolder+filename): os.remove(avgfolder+filename)
      assert os.path.exists(avgfolder)
      sink = DatasetNetCDF(name='WRF Climatology', folder=avgfolder, filelist=[filename], atts=source.atts, mode='w')
      sink.atts.period = periodstr 
      
      # determine averaging interval
      offset = source.time.getIndex(period[0]-1979)/12 # origin of monthly time-series is at January 1979 
      # initialize processing
#       CPU = CentralProcessingUnit(source, sink, varlist=['precip', 'T2'], tmp=True) # no need for lat/lon
      CPU = CentralProcessingUnit(source, sink, varlist=None, tmp=True) # no need for lat/lon
      
      # start processing climatology
      CPU.Climatology(period=period[1]-period[0], offset=offset, flush=False)
      
      # reproject and resample (regrid) dataset
      if xlon is not None and ylat is not None:
        CPU.Regrid(xlon=xlon, ylat=ylat, flush=False)
        print('    ---   (%3.2f,  %3i x %3i)   ---   '%(dlon, len(lon), len(lat)))
      
      
      # sync temporary storage with output
      CPU.sync(flush=True)
  
  #     # make new masks
  #     sink.mask(sink.landmask, maskSelf=False, varlist=['snow','snowh','zs'], invert=True, merge=False)
  
      # add names and length of months
      sink.axisAnnotation('name_of_month', name_of_month, 'time', 
                          atts=dict(name='name_of_month', units='', long_name='Name of the Month'))
      #print '   ===   month   ===   '
      sink += VarNC(sink.dataset, name='length_of_month', units='days', axes=(sink.time,), data=days_per_month,
                    atts=dict(name='length_of_month',units='days',long_name='Length of Month'))
      
      # close... and write results to file
      print('\n Writing to: \'%s\'\n'%filename)
      sink.sync()
      sink.close()
      # print dataset
      print('')
      print(sink)     
      