'''
Created on 2013-08-24 

Unittest for the PyGeoDat main package geodata.

@author: Andre R. Erler, GPL v3
'''

import unittest
import netCDF4 as nc
import numpy as np
import numpy.ma as ma
import os

# import modules to be tested
from geodata.nctools import writeNetCDF
from geodata.misc import isZero, isOne, isEqual
from geodata.base import Variable, Axis, Dataset

class BaseVarTest(unittest.TestCase):  
  
  # some test parameters (TestCase does not take any arguments)  
  plot = False # whether or not to display plots 
  stats = False # whether or not to compute stats on data
  
  def setUp(self):
    ''' create Axis and a Variable instance for testing '''
    # some setting that will be saved for comparison
    self.size = (2,3,4) # size of the data array and axes
    te, ye, xe = self.size
    self.atts = dict(name = 'test',units = 'n/a',FillValue=-9999)
    self.data = np.random.random(self.size)   
    # create axis instances
    t = Axis(name='t', units='none', coord=(1,te,te))
    y = Axis(name='y', units='none', coord=(1,ye,ye))
    x = Axis(name='x', units='none', coord=(1,xe,xe))
    self.axes = (t,y,x)
    # create axis and variable instances (make *copies* of data and attributes!)
    self.var = Variable(name=self.atts['name'],units=self.atts['units'],axes=self.axes,
                        data=self.data.copy(),atts=self.atts.copy())
    self.rav = Variable(name=self.atts['name'],units=self.atts['units'],axes=self.axes,
                        data=self.data.copy(),atts=self.atts.copy())
    # check if data is loaded (future subclasses may initialize without loading data by default)
    if not self.var.data: self.var.load(self.data.copy()) # again, use copy!
    if not self.rav.data: self.rav.load(self.data.copy()) # again, use copy!
        
  def tearDown(self):
    ''' clean up '''     
    self.var.unload() # just to do something... free memory
    self.rav.unload()
    
  ## basic tests every variable class should pass

  def testPrint(self):
    ''' just print the string representation '''
    assert self.var.prettyPrint()
    print('')
    s = str(self.var)
    print s
    print('')

  def testLoad(self):
    ''' test data loading and unloading '''
    # get test objects
    var = self.var
    # unload and load test
    var.unload()
    var.load(self.data.copy())
    assert self.size == var.shape
    assert isEqual(self.data, var.data_array)
    
  def testCopy(self):
    ''' test copy and deepcopy of variables (and axes) '''
    # get copy of variable
    var = self.var.deepcopy(name='different') # deepcopy calls copy
    # check identity
    assert var != self.var
    assert var.name == 'different' and self.var.name != 'different'      
    assert (var.units == self.var.units) and (var.units is self.var.units) # strings are immutable...
    assert (var.atts is not self.var.atts) and (var.atts == self.var.atts) # ...dictionaries are not
    for key,value in var.atts.iteritems():
      assert np.all(value == self.var.atts[key])
    assert isEqual(var.data_array,self.var.data_array) 
    # change array
    var.data_array += 1 # test if we have a true copy and not just a reference 
    assert not isEqual(var.data_array,self.var.data_array)
    
  def testAttributes(self):
    ''' test handling of attributes '''
    # get test objects
    var = self.var; atts = self.atts
    # test getattr
    assert (atts['name'],atts['units']) == (var.name,var.units)
    # test setattr
    var.atts.comments = 'test'; var.plot['comments'] = 'test'
    assert var.plot.comments == var.atts['comments']      
    #     print 'Name: %s, Units: %s, Missing Values: %s'%(var.name, var.units, var._FillValue)
    #     print 'Comments: %s, Plot Comments: %s'%(var.Comments,var.plotatts['plotComments'])

  def testIndexing(self):
    ''' test indexing and slicing '''
    # get test objects
    var = self.var
    # indexing (getitem) test  
    if var.ndim == 3:  
      assert isEqual(self.data[1,1,1], var[1,1,1], masked_equal=True)
      assert isEqual(self.data[1,:,1:-1], var[1,:,1:-1], masked_equal=True)
      
  def testBroadcast(self):
    ''' test reordering, reshaping, and broadcasting '''
    # get test objects
    var = self.var
    z = Axis(name='z', units='none', coord=(1,5,5)) # new axis    
    new_axes = var.axes[0:1] + (z,) + var.axes[-1:0:-1] # dataset independent
    new_axes_names = tuple([ax.name for ax in new_axes])
    # test reordering and reshaping/extending (using axis names)
    new_shape = tuple([var.shape[var.axisIndex(ax)] if var.hasAxis(ax) else 1 for ax in new_axes]) 
    data = var.getArray(axes=new_axes_names, broadcast=False, copy=True)
    #print var.shape # this is what it was
    #print data.shape # this is what it is
    #print new_shape 
    assert data.shape == new_shape 
    # test broadcasting to a new shape (using Axis instances) 
    new_shape = tuple([len(ax) for ax in new_axes]) # this is the shape we should get
    data = var.getArray(axes=new_axes, broadcast=True, copy=True)
    #print var.shape # this is what it was
    #print data.shape # this is what it is
    #print new_shape # this is what it should be
    assert data.shape == new_shape 
      
  def testUnaryArithmetic(self):
    ''' test unary arithmetic functions '''
    # get test objects
    var = self.var
    # arithmetic test
    var += 2.
    var -= 2.
    var *= 2.
    var /= 2.
    # test results
    #     print (self.data.filled() - var.data_array.filled()).max()
    assert isEqual(self.data, var.data_array)
    
  def testAxis(self):
    ''' test stuff related to axes '''
    # get test objects
    var = self.var
    # test contains 
    for ax,n in zip(self.axes,self.size):
      assert ax in var.axes
      assert len(ax) == n
#       if ax in var: print '%s is the %i. axis and has length %i'%(ax.name,var[ax]+1,len(ax))

  def testMask(self):
    ''' test masking and unmasking of data '''
    # get test objects
    var = self.var; rav = self.rav
    masked = var.masked
    mask = var.getMask()
    data = var.getArray(unmask=True, fillValue=-9999)
    # test unmasking and masking again
    var.unmask(fillValue=-9999)
    assert isEqual(data, var[:]) # trivial
    var.mask(mask=mask)
    assert isEqual(self.data, var.getArray(unmask=(not masked)))
    # test masking with a variable
    var.unmask(fillValue=-9999)
    assert isEqual(data, var[:]) # trivial
    var.mask(mask=rav)
    assert isEqual(ma.array(self.data,mask=(rav.data_array>0)), var.getArray(unmask=False))
    
    
  def testBinaryArithmetic(self):
    ''' test binary arithmetic functions '''
    # get test objects
    var = self.var
    rav = self.rav
    # arithmetic test
    a = var + rav
    assert isEqual(self.data*2, a.data_array)
    s = var - rav
    assert isZero(s.data_array)
    m = var * rav
    assert isEqual(self.data**2, m.data_array)
    if (rav.data_array == 0).any(): # can't divide by zero!
      if (rav.data_array != 0).any():  # test masking: mask zeros
        rav.mask(np.logical_not(rav.data_array), fillValue=rav.fillValue, merge=True)
      else: raise TypeError, 'Cannot divide by all-zero field!' 
    d = var / rav
    assert isOne(d.data_array)
    # test results
    #     print (self.data.filled() - var.data_array.filled()).max()
#     assert isEqual(np.ones_like(self.data), d.data_array)
#     assert isOne(d.data_array)  


class BaseDatasetTest(unittest.TestCase):  
  
  # some test parameters (TestCase does not take any arguments)  
  plot = False # whether or not to display plots 
  stats = False # whether or not to compute stats on data
  
  def setUp(self):
    ''' create Dataset with Axes and a Variables for testing '''
    # some setting that will be saved for comparison
    self.size = (3,3,3) # size of the data array and axes
    te, ye, xe = self.size
    self.atts = dict(name = 'var',units = 'n/a',FillValue=-9999)
    self.data = np.random.random(self.size)   
    # create axis instances
    t = Axis(name='t', units='none', coord=(1,te,te))
    y = Axis(name='y', units='none', coord=(1,ye,ye))
    x = Axis(name='x', units='none', coord=(1,xe,xe))
    self.axes = (t,y,x)
    # create axis and variable instances (make *copies* of data and attributes!)
    var = Variable(name='var',units=self.atts['units'],axes=self.axes,
                        data=self.data.copy(),atts=self.atts.copy())
    rav = Variable(name='rav',units=self.atts['units'],axes=self.axes,
                        data=self.data.copy(),atts=self.atts.copy())
    self.var = var; self.rav = rav 
    # make dataset
    self.dataset = Dataset(varlist=[var, rav])
    # check if data is loaded (future subclasses may initialize without loading data by default)
    if not self.var.data: self.var.load(self.data.copy()) # again, use copy!
    if not self.rav.data: self.rav.load(self.data.copy()) # again, use copy!
        
  def tearDown(self):
    ''' clean up '''     
    self.var.unload() # just to do something... free memory
    self.rav.unload()
    
  ## basic tests every variable class should pass

  def testPrint(self):
    ''' just print the string representation '''
    assert self.dataset.__str__()
    print('')
    print(self.dataset)
    print('')
    
  def testWrite(self):
    ''' write test dataset to a netcdf file '''    
    folder = '/media/tmp/' # RAM disk
    filename = folder + 'test.nc'
    if os.path.exists(filename): os.remove(filename)
    # test object
    dataset = self.dataset
    # add non-conforming attribute
    dataset.atts['test'] = [1,'test',3]
    # write file
#     print dataset.y
#     print dataset.y.getArray(), len(dataset.y)
    writeNetCDF(dataset,filename,writeData=True)
    # check that it is OK
    assert os.path.exists(filename)
    ncfile = nc.Dataset(filename)
    assert ncfile
    print(ncfile)
    ncfile.close()
    if os.path.exists(filename): os.remove(filename)
  
  def testAddRemove(self):
    ''' test adding and removing variables '''
    # test objects: var and ax
    name='test'
    ax = Axis(name='ax', units='none')
    var = Variable(name=name,units='none',axes=(ax,))
    dataset = self.dataset
    le = len(dataset)
    # add/remove axes
    dataset.addVariable(var)
    assert dataset.hasVariable(var)
    assert dataset.hasAxis(ax)
    assert len(dataset) == le + 1
    dataset.removeAxis(ax) # should not work now
    assert dataset.hasAxis(ax)    
    dataset.removeVariable(var)
    assert dataset.hasVariable(name) == False
    assert len(dataset) == le
    dataset.removeAxis(ax)
    assert dataset.hasAxis(ax) == False
    
  def testContainer(self):
    ''' test basic container functionality '''
    # test objects: vars and axes
    dataset = self.dataset
    # check container properties 
    assert len(dataset.variables) == len(dataset)
    for varname,varobj in dataset.variables.iteritems():
      assert varname in dataset
      assert varobj in dataset
    # test get, del, set
    varname = dataset.variables.keys()[0]
    var = dataset[varname]
    assert isinstance(var,Variable) and var.name == varname
    del dataset[varname]
    assert not dataset.hasVariable(varname)
    dataset[varname] = var
    assert dataset.hasVariable(varname)


# import modules to be tested
from geodata.netcdf import VarNC, AxisNC, DatasetNetCDF

class NetCDFVarTest(BaseVarTest):  
  
  # some test parameters (TestCase does not take any arguments)
  dataset = 'NARR' # dataset to use (also the folder name)
  RAM = True # base folder for file operations
  plot = False # whether or not to display plots 
  stats = False # whether or not to compute stats on data
  
  def setUp(self):
    if self.RAM: folder = '/media/tmp/'
    else: folder = '/home/DATA/DATA/%s/'%self.dataset # dataset name is also in folder name
    # select dataset
    if self.dataset == 'GPCC': # single file
      filelist = ['gpcc_test/full_data_v6_precip_25.nc'] # variable to test
      varlist = ['p']
      ncfile = filelist[0]; ncvar = varlist[0]      
    elif self.dataset == 'NARR': # multiple files
      filelist = ['narr_test/air.2m.mon.ltm.nc', 'narr_test/prate.mon.ltm.nc', 'narr_test/prmsl.mon.ltm.nc'] # variable to test
      varlist = ['air','prate','prmsl','lon','lat']
      ncfile = filelist[0]; ncvar = varlist[0]
    # load a netcdf dataset, so that we have something to play with      
    self.ncdata = nc.Dataset(folder+ncfile,mode='r')
    # load variable
    ncvar = self.ncdata.variables[ncvar]      
    # get dimensions and coordinate variables
    size = tuple([len(self.ncdata.dimensions[dim]) for dim in ncvar.dimensions])
    axes = tuple([AxisNC(self.ncdata.variables[dim], length=le) for dim,le in zip(ncvar.dimensions,size)]) 
    # initialize netcdf variable 
    self.ncvar = ncvar; self.axes = axes
    self.var = VarNC(ncvar, axes=axes, load=True)    
    self.rav = VarNC(ncvar, axes=axes, load=True) # second variable for binary operations    
    # save the original netcdf data
    self.data = ncvar[:].copy() #.filled(0)
    self.size = tuple([len(ax) for ax in axes])
    # construct attributes dictionary from netcdf attributes
    self.atts = { key : self.ncvar.getncattr(key) for key in self.ncvar.ncattrs() }
    self.atts['name'] = self.ncvar._name
    if 'units' not in self.atts: self.atts['units'] = '' 
      
  def tearDown(self):  
    self.var.unload()   
    self.ncdata.close()
  
  ## specific NetCDF test cases

  def testScaling(self):
    ''' test scale and offset operations '''
    # get test objects
    var = self.var
    # unload and change scale factors    
    var.unload()
    var.scalefactor = 2.
    var.offset = 100.
    # load data with new scaling
    var.load()
    assert self.size == var.shape
    assert isEqual((self.data+100.)*2, var.data_array)
  
  def testLoadSlice(self):
    ''' test loading of slices '''
    # get test objects
    var = self.var
    var.unload()
    # load slice
    if var.ndim == 3:
      sl = (slice(0,12,1),slice(20,50,5),slice(70,140,15))
      var.load(sl)
      assert (12,6,5) == var.shape
      if var.masked:
        assert isEqual(self.data.__getitem__(sl), var.data_array)
      else:
        assert isEqual(self.data.__getitem__(sl).filled(var.fillValue), var.data_array)
  
  def testIndexing(self):
    ''' test indexing and slicing '''
    # get test objects
    var = self.var
    # indexing (getitem) test    
    if var.ndim == 3:
      assert isEqual(self.data[1,1,1], var[1,1,1])
      assert isEqual(self.data[1,:,1:-1], var[1,:,1:-1])
    # test axes

  def testFileAccess(self):
    ''' test access to data without loading '''
    # get test objects
    var = self.var
    var.unload()
    # access data
    data = var[:]
    assert data.shape == self.data.shape
    assert isEqual(self.data[:], data)
    # assert no data
    assert not var.data
    assert var.data_array is None
  

class DatasetNetCDFTest(BaseDatasetTest):  
  
  # some test parameters (TestCase does not take any arguments)
  dataset = 'NARR' # dataset to use (also the folder name)
  RAM = True # base folder for file operations
  plot = False # whether or not to display plots 
  stats = False # whether or not to compute stats on data
  
  def setUp(self):
    if self.RAM: folder = '/media/tmp/'
    else: folder = '/home/DATA/DATA/%s/'%self.dataset # dataset name is also in folder name
    # select dataset
    name = self.dataset
    if self.dataset == 'GPCC': # single file      
      filelist = ['gpcc_test/full_data_v6_precip_25.nc'] # variable to test
      varlist = ['p']; varatts = None
      ncfile = filelist[0]; ncvar = varlist[0]      
    elif self.dataset == 'NARR': # multiple files
      filelist = ['narr_test/air.2m.mon.ltm.nc', 'narr_test/prate.mon.ltm.nc', 'narr_test/prmsl.mon.ltm.nc'] # variable to test
      varlist = ['air','prate','prmsl','lon','lat']
      varatts = dict(air=dict(name='T2'),prmsl=dict(name='pmsl'))
      ncfile = filelist[0]; ncvar = varlist[0]
    # load a netcdf dataset, so that we have something to play with      
    self.ncdata = nc.Dataset(folder+ncfile,mode='r')
    self.dataset = DatasetNetCDF(name=name,folder=folder,filelist=filelist,varlist=varlist,varatts=varatts)
    # load a sample variable directly
    ncvar = self.ncdata.variables[ncvar]
    # get dimensions and coordinate variables
    size = tuple([len(self.ncdata.dimensions[dim]) for dim in ncvar.dimensions])
    axes = tuple([AxisNC(self.ncdata.variables[dim], length=le) for dim,le in zip(ncvar.dimensions,size)]) 
    # initialize netcdf variable 
    self.ncvar = ncvar; self.axes = axes
    self.var = VarNC(ncvar, axes=axes, load=True)    
    # save the original netcdf data
    self.data = ncvar[:].copy() #.filled(0)
    self.size = tuple([len(ax) for ax in axes])
    # construct attributes dictionary from netcdf attributes
    self.atts = { key : self.ncvar.getncattr(key) for key in self.ncvar.ncattrs() }
    self.atts['name'] = self.ncvar._name
    if 'units' not in self.atts: self.atts['units'] = '' 
      
  def tearDown(self):  
    self.var.unload()   
    self.ncdata.close()
  
  ## specific NetCDF test cases
      
  def testLoad(self):
    ''' test loading and unloading of data '''
    # test objects: vars and axes
    dataset = self.dataset
    # load data
    dataset.load()
    assert all([var.data for var in dataset])
    # unload data
    dataset.unload()
    assert all([not var.data for var in dataset])

  def testCreate(self):
    ''' test creation of a new NetCDF dataset and file '''
    folder = '/media/tmp/' # RAM disk
    filename = folder + 'test.nc'
    if os.path.exists(filename): os.remove(filename)
    # create NetCDF Dataset
    dataset = DatasetNetCDF(filelist=[filename],mode='w')
#     print(dataset)
    # add some random variables and attribute
    dataset.atts.test = 'test'
    dataset.sync()
#     print(dataset)
    # synchronize with disk and close     
    dataset.close()
    # check that it is OK
    assert os.path.exists(filename)
    ncfile = nc.Dataset(filename)
    assert ncfile
    print(ncfile)
    ncfile.close()


# import modules to be tested
from geodata.gdal import addGDALtoVar, addGDALtoDataset
from datasets.NARR import projdict

class GDALVarTest(NetCDFVarTest):  
  
  # some test parameters (TestCase does not take any arguments)
  dataset = 'NARR' # dataset to use (also the folder name)
  RAM = True # base folder for file operations
  plot = False # whether or not to display plots 
  stats = False # whether or not to compute stats on data
  # some projection settings for tests
  projection = ''
  
  def setUp(self):
    super(GDALVarTest,self).setUp()
    # add GDAL functionality to variable
    if self.dataset == 'NARR':
      self.var = addGDALtoVar(self.var, projection=projdict)
    else: 
      self.var = addGDALtoVar(self.var)
      
  def tearDown(self):  
    super(GDALVarTest,self).tearDown()
  
  ## specific GDAL test cases

  def testAddProjection(self):
    ''' test function that adds projection features '''
    # get test objects
    var = self.var # NCVar object
#     print var.xlon[:]
#     print var.ylat[:]
    print var.geotransform # need to subtract false easting and northing!
    # trivial tests
    assert var.gdal
    if self.dataset == 'NARR': assert var.isProjected == True
    if self.dataset == 'GPCC': assert var.isProjected == False
    assert var.geotransform
    data = var.getGDAL()
    assert data is not None
    assert data.ReadAsArray()[:,:,:].shape == (var.bands,)+var.mapSize 


class DatasetGDALTest(DatasetNetCDFTest):  
  
  # some test parameters (TestCase does not take any arguments)
  dataset = 'NARR' # dataset to use (also the folder name)
  RAM = True # base folder for file operations
  plot = False # whether or not to display plots 
  stats = False # whether or not to compute stats on data
  
  def setUp(self):
    super(DatasetGDALTest,self).setUp()
    # add GDAL functionality to variable
    if self.dataset.name == 'NARR':
      self.dataset = addGDALtoDataset(self.dataset, projection=projdict) # projected
    else: 
      self.dataset.name = addGDALtoDataset(self.dataset) # not projected
      
  def tearDown(self):  
    super(DatasetGDALTest,self).tearDown()
  
  ## specific GDAL test cases

  def testAddProjection(self):
    ''' test function that adds projection features '''
    # get test objects
    dataset = self.dataset # dataset object
#     print var.xlon[:]
#     print var.ylat[:]
    # trivial tests
    assert dataset.gdal
    assert dataset.projection
    assert dataset.geotransform
    assert len(dataset.geotransform) == 6 # need to subtract false easting and northing!
    if self.dataset.name == 'NARR': 
      assert dataset.isProjected == True
      assert dataset.xlon == dataset.x and dataset.ylat == dataset.y    
    if self.dataset.name == 'GPCC': 
      assert dataset.isProjected == False
      assert dataset.xlon == dataset.lon and dataset.ylat == dataset.lat
    # check variables
    for var in dataset.variables.values():
      assert (var.ndim >= 2 and var.hasAxis(dataset.xlon) and var.hasAxis(dataset.ylat)) == var.gdal
    
if __name__ == "__main__":

    # construct dictionary of test classes defined above
    test_classes = dict()
    local_values = locals().copy()
    for key,val in local_values.iteritems():
      if key[-4:] == 'Test':
        test_classes[key[:-4]] = val

    # tests to be performed
    # list of variable tests
#     tests = ['BaseVar'] 
#     tests = ['NetCDFVar']
#     tests = ['GDALVar']
    # list of dataset tests
#     tests = ['BaseDataset']
#     tests = ['DatasetNetCDF']
    tests = ['DatasetGDAL']    
    
    # run tests
    for test in tests:
      s = unittest.TestLoader().loadTestsFromTestCase(test_classes[test])
      unittest.TextTestRunner(verbosity=2).run(s)