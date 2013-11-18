'''
Created on 2013-11-14

A simple script to plot basin-averaged monthly climatologies. 

@author: Andre R. Erler, GPL v3
'''

# external imports
import numpy as np
import numpy.ma as ma
import matplotlib.pylab as pyl
import matplotlib as mpl
mpl.rc('lines', linewidth=1.)
mpl.rc('font', size=10)
# internal imports
# PyGeoDat stuff
from datasets.GPCC import loadGPCC
from datasets.CRU import loadCRU
from datasets.WRF_experiments import exps as WRF_exps
from datasets.common import loadDatasets # for annotation
from plotting.settings import getFigureSettings, getVariableSettings
# ARB project related stuff
from plotting.ARB_settings import getARBsetup, arb_figure_folder, arb_map_folder

# settings
folder = arb_figure_folder
lprint = True 

## start computation
if __name__ == '__main__':
  
  ## settings
  expset = 'ens-2050'
  plottype = 'flxrof'
  tag = '5yrs'
  ljoined = True
  period = 5
  domain = 2
  grid='arb2_d{0:2d}'.format(domain)
  varatts = None # dict(Runoff=dict(name='runoff'))
  xlabel = r'Seasonal Cycle [Month]'; xlim = (1,12)
  
  ## datasets
  if expset == 'mix': 
    explist = ['max','max-2050','ctrl','seaice-2050']
  elif expset == 'ens': 
    explist = ['max','max-A','max-B','max-C']
  elif expset == 'ens-2050': 
    explist = ['max-2050','max-A-2050','max-B-2050','max-C-2050']

  
  ## variable settings
  flxlabel = r'Water Flux [$10^6$ kg/s]'; flxlim = (-2,6)
  if plottype == 'flux':
    varlist = ['waterflx','snwmlt','p-et','precip']; filetypes = ['srfc','hydro']; 
    lsum = True; leg = (2,3); ylabel = flxlabel; ylim = flxlim
  elif plottype == 'temp':
    varlist = ['T2','Tmin','Tmax']; filetypes = ['srfc','xtrm']; 
    lsum = False; leg = (2,8); ylabel = 'Temperature [K]'; ylim = (250,300)
  elif plottype == 'precip':
    varlist = ['p-et','precip','liqprec','solprec']; filetypes = ['hydro']; 
    lsum = True; leg = (2,3); ylabel = flxlabel; ylim = flxlim
  elif plottype == 'flxrof':
    varlist = ['waterflx','runoff','snwmlt','p-et','precip']; filetypes = ['srfc','hydro','lsm']; 
    lsum = True; leg = (2,1); ylabel = flxlabel; ylim = flxlim
  elif plottype == 'runoff':
    varlist = ['ugroff','runoff','sfroff']; filetypes = ['lsm']; 
    lsum = True; leg = (2,1); ylabel = flxlabel; ylim = flxlim
  
  ## load data  
  exps, titles = loadDatasets(explist, n=None, varlist=varlist, titles=None, periods=period, domains=domain, 
               grids='arb2_d02', resolutions=None, filetypes=filetypes, lWRFnative=True, ltuple=False)
  ref = exps[0]; nlen = len(exps)
  # observations
  cru = loadCRU(period=period, grid='arb2_d02', varlist=varlist, varatts=varatts)
  gpcc = loadGPCC(period=None, grid='arb2_d02', varlist=varlist, varatts=varatts)
  print ref
  
  ## apply basin mask
  for exp in exps:
    exp.load(); exp.maskShape(name='Athabasca_River_Basin')
  print 
  
  if len(cru.variables) > 0: 
    cru.load(); cru.maskShape(name='Athabasca_River_Basin')
  if len(gpcc.variables) > 0: 
    gpcc.load(); gpcc.maskShape(name='Athabasca_River_Basin')
  print 
  
  
  # display
#   pyl.imshow(np.flipud(dataset.Athabasca_River_Basin.getArray()))
#   pyl.imshow(np.flipud(dataset.precip.getMapMask()))
#   pyl.colorbar(); 
  # scale factor
  if lsum: S = ( 1 - ref.Athabasca_River_Basin.getArray() ).sum() * (ref.atts.DY*ref.atts.DY) / 1.e6
  else: S = 1.

  ## setting up figure
  # figure parameters for saving
  sf, figformat, margins, subplot, figsize = getFigureSettings(nlen, cbar=False)
  # make figure and axes
  f = pyl.figure(facecolor='white', figsize=figsize)
  axes = []
  for n in xrange(nlen):
    axes.append(f.add_subplot(subplot[0],subplot[1],n+1))
  f.subplots_adjust(**margins) # hspace, wspace
  
  # loop over axes
  n = -1 # axes counter
  for i in xrange(subplot[0]):
    for j in xrange(subplot[1]):
      n += 1 # count up
      # select axes
      ax,exp,title = axes[n],exps[n],titles[n]
      # alignment
      if j == 0 : left = True
      else: left = False 
      if i == subplot[0]-1: bottom = True
      else: bottom = False           
    
      # make plots
      time = exp.time.coord # time axis
      wrfplt = []; wrfleg = [] 
      obsplt = []; obsleg = []
      # loop over vars    
      for var in varlist:
        # define color
        if var == 'T2': color = 'green'
        elif var == 'precip': color = 'green'
        elif var == 'liqprec': color = 'blue'
        elif var == 'solprec': color = 'cyan'
        elif var == 'p-et': color = 'red'
        elif var == 'waterflx': color = 'blue'
        elif var == 'snwmlt': color = 'coral'
        elif var == 'runoff': color = 'purple'
        elif var == 'ugroff': color = 'green'
        elif var == 'sfroff': color = 'coral'
        elif var == 'Tmax': color = 'red'
        elif var == 'Tmin': color = 'blue'          
        # compute spatial average
        vardata = exp.variables[var].mean(x=None,y=None)
        wrfplt.append(ax.plot(time, S*vardata.getArray(), color=color, label=var)[0])
        wrfleg.append(var)
        print
        print exp.name, vardata.name, S*vardata.getArray().mean()
        if cru.hasVariable(var, strict=False):
          # compute spatial average for CRU
          vardata = cru.variables[var].mean(x=None,y=None)
          label = '%s (%s)'%(var,cru.name)
          obsplt.append(ax.plot(time, S*vardata.getArray(), 'o', color=color, label=label)[0])
          obsleg.append(label)
          print
          print cru.name, vardata.name, S*vardata.getArray().mean()
        if gpcc.hasVariable(var, strict=False):
          # compute spatial average for GPCC
          label = '%s (%s)'%(var,gpcc.name)
          vardata = gpcc.variables[var].mean(x=None,y=None)
          obsplt.append(ax.plot(time, S*vardata.getArray(), 'o', color='purple', label=label)[0])
          obsleg.append(label)
          print
          print gpcc.name, vardata.name, S*vardata.getArray().mean()
        # axes
        labelpad = lambda lim: 3 # -8 if lim[0] < 0 else 3       
        ax.set_xlim(xlim[0],xlim[1])
        if left: ax.set_ylabel(ylabel, labelpad=labelpad(ylim))
        else: ax.set_yticklabels([])          
        ax.set_ylim(ylim[0],ylim[1])
        if bottom: ax.set_xlabel(xlabel, labelpad=labelpad(xlim))
        else: ax.set_xticklabels([])
        # legend
        if not ljoined:
          legargs = dict(labelspacing=0.125, handlelength=1.5, handletextpad=0.5, fancybox=True)
          wrflegend = ax.legend(wrfplt, wrfleg, loc=leg[0], **legargs)       
          obslegend = ax.legend(obsplt, obsleg, loc=leg[1], **legargs)
          ax.add_artist(wrflegend); ax.add_artist(obslegend)
        # annotation
        #ax.set_title(title+' ({})'.format(exp.name))
        ax.set_title(title)
        if var in ['p-et', 'precip', 'runoff']:
          ax.axhline(620,linewidth=0.5, color='k')
          ax.axhline(0,linewidth=0.5, color='0.5')
    
  # add common legend
  if ljoined:
    ax = f.add_axes([0, 0, 1,0.1])
    ax.set_frame_on(False); ax.axes.get_yaxis().set_visible(False); ax.axes.get_xaxis().set_visible(False)
    margins['bottom'] = margins['bottom'] + 0.1; f.subplots_adjust(**margins)
    legargs = dict(labelspacing=0.125, handlelength=1.75, handletextpad=0.75, fancybox=True)
    legend = ax.legend(wrfplt+obsplt, wrfleg+obsleg, loc=10, ncol=4, borderaxespad=0., **legargs)  
    
  # average discharge below Fort McMurray: 620 m^3/s
    
  # save figure to disk
  if lprint:
    if tag: filename = 'ARB_{0:s}_{1:s}_{2:s}.png'.format(plottype,expset,tag)
    else: filename = 'ARB_{0:s}_{1:s}.png'.format(plottype,expset)
    print('\nSaving figure in '+filename)
    f.savefig(folder+filename, **sf) # save figure to pdf
    print(folder)
  
  ## show plots after all iterations
  pyl.show()