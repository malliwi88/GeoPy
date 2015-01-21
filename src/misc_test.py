'''
Created on 2015-01-19 

Unittest for assorted PyGeoDat components not included elsewhere.

@author: Andre R. Erler, GPL v3
'''

import unittest
import numpy as np
import os, sys, gc
import multiprocessing
import logging
from time import sleep


# import geodata modules
from geodata.nctools import writeNetCDF
from geodata.misc import isZero, isOne, isEqual
from geodata.base import Variable, Axis, Dataset
from datasets.common import data_root
# import modules to be tested


# RAM disk settings ("global" variable)
RAM = True # whether or not to use a RAM disk
ramdisk = '/media/tmp/' # folder where RAM disk is mounted
NP = 2
ldebug = False


## tests for multiprocess module
class MultiProcessTest(unittest.TestCase):  
   
  def setUp(self):
    ''' create two test variables '''
    pass
      
  def tearDown(self):
    ''' clean up '''
    gc.collect()

  def testApplyAlongAxis(self):
    ''' test parallelized version of Numpy's apply_along_axis '''    
    from processing.multiprocess import apply_along_axis, test_aax, test_noaax
    import functools
    
    def run_test(fct, kw=0, axis=1, laax=True):
      ff = functools.partial(fct, kw=kw)
      shape = (500,100)
      data = np.arange(np.prod(shape), dtype='float').reshape(shape)
      assert data.shape == shape
      # parallel implementation using my wrapper
      pres = apply_along_axis(ff, axis, data, NP=2, ldebug=True, laax=laax)
      print pres.shape
      assert pres.shape == data.shape
      assert isZero(pres.mean(axis=axis)+kw) and isZero(pres.std(axis=axis)-1.)
      # straight-forward numpy version
      res = np.apply_along_axis(ff, axis, data)
      assert res.shape == data.shape
      assert isZero(res.mean(axis=axis)+kw) and isZero(res.std(axis=axis)-1.)
      # final test
      assert isEqual(pres, res) 
      
    # run tests 
    run_test(test_noaax, kw=1, laax=False) # without Numpy's apply_along_axis
    run_test(test_aax, kw=1, laax=True) # Numpy's apply_along_axis

  
  def testAsyncPool(self):
    ''' test asyncPool wrapper '''    
    from processing.multiprocess import asyncPoolEC, test_func_dec, test_func_ec
    args = [(n,) for n in xrange(5)]
    kwargs = dict(wait=1)
    ec = asyncPoolEC(test_func_dec, args, kwargs, NP=NP, ldebug=ldebug, ltrialnerror=True)
    assert ec == 0 
    ec = asyncPoolEC(test_func_ec, args, kwargs, NP=NP, ldebug=ldebug, ltrialnerror=True)
    assert ec == 4
    ec = asyncPoolEC(test_func_ec, args, kwargs, NP=NP, ldebug=ldebug, ltrialnerror=False)
    assert ec == 0
    

  
## tests related to loading datasets
class DatasetsTest(unittest.TestCase):  
   
  def setUp(self):
    ''' create two test variables '''
    pass
      
  def tearDown(self):
    ''' clean up '''
    gc.collect()

  def testExpArgList(self):
    ''' test function to expand argument lists '''    
    from datasets.common import expandArgumentList
    # test arguments
    args1 = [0,1,2]; args2 = ['0','1','2']; args3 = ['test']*3; arg4 = 'static1'; arg5 = 'static2' 
    explist = ['arg1','arg2','arg3']
    # test inner prodct expansion
    arg_list = expandArgumentList(arg1=args1, arg2=args2, arg3=args3, arg4=arg4, arg5=arg5,
                                  expand_list=explist, lproduct='inner')
    assert len(arg_list) == len(args1) and len(arg_list) == len(args2)
    for args,arg1,arg2,arg3 in zip(arg_list,args1,args2,args3):
      assert args['arg1'] == arg1
      assert args['arg2'] == arg2
      assert args['arg3'] == arg3
      assert args['arg4'] == arg4
      assert args['arg5'] == arg5
    # test outer prodct expansion
    arg_list = expandArgumentList(arg1=args1, arg2=args2, arg3=args3, arg4=arg4, arg5=arg5,
                                  expand_list=explist, lproduct='outer')
    assert len(arg_list) == len(args1) * len(args2) * len(args3)
    n = 0
    for arg1 in args1:
      for arg2 in args2:
        for arg3 in args3:
          args = arg_list[n]
          assert args['arg1'] == arg1
          assert args['arg2'] == arg2
          assert args['arg3'] == arg3
          assert args['arg4'] == arg4
          assert args['arg5'] == arg5
          n += 1
    assert n == len(arg_list)
    
  def testLoadDataset(self):
    ''' test universal dataset loading function '''
    from datasets.common import loadDataset, loadClim, loadStnTS 
    pcic = loadClim(name='PCIC', folder=None, resolution=None, period=None, grid='arb2_d02', varlist=['precip'], 
                    varatts=None, lautoregrid=False)
    assert isinstance(pcic, Dataset)
    assert 'precip' in pcic
    assert pcic.name == 'PCIC'
    assert pcic.gdal and pcic.isProjected
#     loadStnTS(name=None, folder=None, resolution=None, varlist=None, station=None, varatts=None):
#     loadDataset(name=None, folder=None, resolution=None, period=None, grid=None, station=None, 
#                 varlist=None, varatts=None, lautoregrid=None, mode='climatology')
    
if __name__ == "__main__":

    
    specific_tests = None
#     specific_tests = ['ApplyAlongAxis']
#     specific_tests = ['AsyncPool']    
#     specific_tests = ['ExpArgList']
    specific_tests = ['LoadDataset']


    # list of tests to be performed
    tests = [] 
    # list of variable tests
#     tests += ['MultiProcess']
    tests += ['Datasets'] 
    

    # construct dictionary of test classes defined above
    test_classes = dict()
    local_values = locals().copy()
    for key,val in local_values.iteritems():
      if key[-4:] == 'Test':
        test_classes[key[:-4]] = val


    # run tests
    report = []
    for test in tests: # test+'.test'+specific_test
      if specific_tests: 
        test_names = ['misc_test.'+test+'Test.test'+s_t for s_t in specific_tests]
        s = unittest.TestLoader().loadTestsFromNames(test_names)
      else: s = unittest.TestLoader().loadTestsFromTestCase(test_classes[test])
      report.append(unittest.TextTestRunner(verbosity=2).run(s))
      
    # print summary
    runs = 0; errs = 0; fails = 0
    for name,test in zip(tests,report):
      #print test, dir(test)
      runs += test.testsRun
      e = len(test.errors)
      errs += e
      f = len(test.failures)
      fails += f
      if e+ f != 0: print("\nErrors in '{:s}' Tests: {:s}".format(name,str(test)))
    if errs + fails == 0:
      print("\n   ***   All {:d} Test(s) successfull!!!   ***   \n".format(runs))
    else:
      print("\n   ###     Test Summary:      ###   \n" + 
            "   ###     Ran {:2d} Test(s)     ###   \n".format(runs) + 
            "   ###      {:2d} Failure(s)     ###   \n".format(fails)+ 
            "   ###      {:2d} Error(s)       ###   \n".format(errs))
    