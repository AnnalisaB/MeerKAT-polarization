#!/usr/bin/python3
#### ##### ##### ##### ##### ##### ##### ##### ##### ##### ##### ##### ##### ##### ##### #####
##### Full-polarisation calibration script for MeerKAT - tested on L band  -written by Annalisa Bonafede - based on Ben Hugo strategy

'''
before running this script, all the fields must have X and Y flipped using the script "correct_parang.py" by B Hugo (UHF, L and S band)
https://github.com/bennahugo/LunaticPolarimetry/blob/master/correct_parang.py
python3 correct_parang.py -f <field> --noparang --applyantidiag <MSfile>
the correct_parang.py script must be run on each field separately
the script writes the output in the CORRECTED_DATA column, so the corrected data needs to be split after the correction

plots are done with shadems https://github.com/ratt-ru/shadeMS

it can be done in flocs as ephem is not imported correctly in casa
'''

import numpy as np
import os, sys, logging

target='PSZ2G313.33'

calms   = './MS_Files/'+target+'-CorrectPang-cal.MS'
targetms= './MS_Files/'+target+'-CorrectPang-target.MS'
ref_ant = 'm002'

#To FLAG: specify flocs singularity (or anthing with aoflagger), the aoflagger strategy and the dir you want to bind
flocs_simg='/iranet/groups/lofar/containers/flocs-latest.simg'
aoflagger_strategy='/'
binding_dir=''


#TO DO: find a way to derive these authomatically - maybe look at the VLA pipeline. NOTE: fcal is bpcal and used for leakage pol as well

fcal  = ['J1939-6342','J0408-6545']
fcal_id='4,1'
bpcal = fcal
bpcal_id= fcal_id
gcal  = 'J1337-1257'
gcal_id='2'
#polarisation calibrator, if you have more than one scan,pick the best one (higher elevation) - scal_xcal
xcal  = 'J1331+3030'
xcal_id='3'
scan_xcal=''
leak_cal='J1939-6342'
leak_cal_id='4'

do_plot=False
do_flags=True
selfcal_xcal=True
model_xcal=True

split_xcal=True
apply_target=True

###### END OF INPUTS (unless you want to change the name ofthe gain tables - see below) ######

##############################
### Logs Setting up and functions
log_file = os.path.join(invis + '.log')
casa_log = os.path.join(invis + '_casa.log')

log_level = logging.DEBUG
logging.basicConfig(filename=log_file,
        format='%(asctime)s %(name)s:%(funcName)s\t%(message)s',
        datefmt='%Y-%m-%d %H:%M', filemode='w',
        level=log_level)
logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))
logger = logging.getLogger(__name__)
old_log_filename = casalog.logfile()
# Point the casa logsink to the new file
casalog.setlogfile(filename=casa_log)
# Delete the old file
os.remove(old_log_filename)
# remove annoying warnings
logging.getLogger("asyncio").setLevel(logging.WARNING)


############################# Set model with SetJy
if 'J0408-6545' in fcal:
    import cal_J0408 

if not os.path.exists("CASA_Tables"):
     os.mkdir("CASA_Tables")
     logger.info("Directory CASA_Tables created. Tables will be saved there.")

# Name your gain tables
gtab_p     = "CASA_Tables/calib.gcal_p"
ktab     = "CASA_Tables/calib.kcal"
gtab_a = "CASA_Tables/calib.gcal_a"
btab     = "CASA_Tables/calib.bandpass"
ftab     = "CASA_Tables/calib.fluxscale"
gtab_sec_p = "CASA_Tables/calib.sec_p"
Ttab_sec = "CASA_Tables/calib.T"
gtab_pol_p= "CASA_Tables/calib.gcal_pol_p"

kxtab    = "CASA_Tables/calib.kcrosscal"
ptab_xf = "CASA_Tables/calib.xf"
ptab_df    = "CASA_Tables/calib.df"
dgen     = "CASA_Tables/calib.leakgen"


################################################################
# Change RECEPTOR_ANGLE : DEFAULT IS -90DEG 

tb.open(calms+'/FEED', nomodify=False)
feed_angle = tb.getcol('RECEPTOR_ANGLE')
new_feed_angle = np.zeros(feed_angle.shape)
tb.putcol('RECEPTOR_ANGLE', new_feed_angle)
tb.close()

clearcal(vis=calms)

for cal in fcal:
    logger.info(f'set jy {cal}')
    if cal == 'J1939-6342':
        logger.info('setting the model for '+ cal)
        setjy(vis = calms, field = '"'+cal+'"', standard = 'Stevens-Reynolds 2016', usescratch = True)

    if cal == 'J0408-6545':
       logger.info(f'setting the model for {cal}') 
       a=-0.9790; b=3.3662; c=-1.1216; d=0.0861
       reffreq,fluxdensity,spix0,spix1,spix2 =  cal_J0408.convert_flux_model(np.linspace(0.9,2,200)*1e9,a,b,c,d)
       setjy(vis = calms, field=cal, spix=[spix0, spix1, spix2, 0], fluxdensity = fluxdensity,  reffreq='%f Hz'%(reffreq),standard='manual',usescratch=True)


if model_xcal ==True:
    if xcal == 'J0521+1638':
        logger.info(f'setting a model for the xcal {xcal}')
        I= 8.33843
        alpha= [-0.4981, -0.1552, -0.0102, 0.0223]
        reffreq= '1.47GHz'
        polfrac= 0.078
        polangle= -0.16755
        rm=0.
    elif xcal =='J1331+3030':
        logger.info(f'setting a model for xcal {xcal}')
        I= 14.7172
        alpha= [-0.4507, -0.1798, 0.0357]
        reffreq= '1.47GHz'
        polfrac= 0.098
        polangle = 0.575959
        rm=0.
    else:
        logger.info(f'Unknown calibrator: {cal}')
        sys.exit()

    setjy(vis=calms, field=xcal, standard="manual", \
          fluxdensity=[I,0,0,0], spix=alpha, reffreq=reffreq, polindex=polfrac, polangle=polangle, rotmeas=rm, usescratch=True)
 

if do_flags==True:
    # initial flags on the data - save initial flag status before
    flagmanager(vis=calms,mode='save',versionname='BeforeBPcal',comment='save flags before bandpass cal')
    os.system(f"singularity run -B {binding_dir} {flocs_simg} aoflagger -strategy {aoflagger_strategy} -fields {bpcal} {calms}")

if do_flags==True:
    range_cal=2
else: range_cal=1

for cal in range(range_cal):

    # Delay calibration  - residual, most taken out at the obs - few nsec typical 
    gaincal(vis = calms, caltable = ktab, selectdata = True,\
            solint = "inf", field = bpcal_id, combine = "",uvrange='',\
            refant = ref_ant, solnorm = False, gaintype = "K",\
            minsnr=5,parang = False)
    
    for ii in range(np.size(bpcal)):
        if ii ==0: append=False
        if ii > 0: append=True
        # phase cal on bandpass calibrator  - phse will be twhrown away - Ben uses infinite time to wash out RFI
        gaincal(vis = calms, caltable = gtab_p, selectdata = True,\
                      solint = "60s", field = bpcal[ii], combine = "",refantmode='strict',\
                      refant = ref_ant, gaintype = "G", calmode = "p",uvrange='',\
                      gaintable = [ktab], gainfield = [''], interp = [''],parang = False,append=append)

        # amp cal on bandpass calibrator
        gaincal(vis = calms, caltable = gtab_a, selectdata = True,\
                      solint = "inf", field = bpcal[ii], combine = "",\
                      refant = ref_ant, gaintype = "G", calmode = "a",uvrange='',\
                      gaintable = [ktab,gtab_p], gainfield = ['',bpcal[ii]], interp = ['',''],parang = False,append=append)

        # ben averages bandpass ober scans - it's more stable he says
        bandpass(vis = calms, caltable = btab, selectdata = True,\
                       solint = "inf", field = bpcal[ii], combine = "", uvrange='',\
                       refant = ref_ant, solnorm = False, bandtype = "B",\
                       gaintable = [ktab,gtab_p,gtab_a], gainfield = ['',bpcal[ii],bpcal[ii]],\
                       interp = ['','',''], parang = False,append=append)

        if (cal==0 and do_flags==True):
                  #plotms(vis=btab, field=bpcal_id,xaxis='chan',yaxis='amp',antenna='',coloraxis='antenna1',plotfile='first_bandpass.png',showgui=False)
                  # undo the flags
                  flagmanager(vis=calms,mode='restore',versionname='BeforeBPcal')
                  # applycal
                  applycal(vis=calms,field=bpcal_id+','+xcal_id+','+gcal_id, gaintable=[ktab,gtab_p,gtab_a,btab])
                  # flag on corrected data
                  #os.system(f"{tricolour_command} {calms} -fs total_power -dc CORRECTED_DATA -c {tricolour_strategy_secondpass}")
                  os.system(f"singularity run -B {binding_dir} {flocs_simg} aoflagger -strategy {aoflagger_strategy} -column CORRECTED_DATA {calms}")
                  #remove tables 
                  os.system(f'rm -rf  {gtab_p} {gtab_a} {btab} {ktab}')



# Calibrate Df   -real part of reference antenna will be set to 0 -
polcal(vis = calms, caltable = ptab_df, selectdata = True,\
           solint = 'inf', field = leak_cal, combine ='scan',uvrange='>150lambda',\
           refant = ref_ant,poltype = 'Df',\
           gaintable = [ktab, gtab_p,gtab_a,btab],\
           gainfield = ['', leak_cal,leak_cal,leak_cal],\
           interp = ['', 'nearest', 'nearest', 'nearest'])

# flag of solutions as caracal is doing Ben would suggest anything above 0.1
flagdata(vis=ptab_df, mode='clip',datacolumn='CPARAM', clipminmax=[-0.6,0.6])

# Apply Df to bpcal, check that after calibration amplitude is reduced NOTE: flagginghaving flagged  RFI  is critical here
applycal(vis=calms,field=leak_cal,gaintable=[ktab,gtab_p,gtab_a,btab,ptab_df],gainfield = ['', leak_cal, leak_cal,leak_cal,''],interp=['','nearest','nearest','nearest',''])


# Check that amplitude of leakage cal is gone down (few %) after calibration
if do_plot ==True:
    
    os.system("shadems --xaxis FREQ  --yaxis CORRECTED_DATA --field "+ leak_cal_id+" --corr XY,YX --png './PLOTS/Df-cal.png' "+calms)
    

'''
    plotms(vis=calms,xaxis='freq',yaxis='amplitude',correlation='XY,YX',field=bpcal,avgscan=True,ydatacolumn='data',avgtime='9999999',plotfile=str(bpcal)+'Df-DATA.png',showgui=False,overwrite=True)

    plotms(vis=calms,xaxis='freq',yaxis='amplitude',correlation='XY,YX',field=bpcal,avgscan=True,ydatacolumn='corrected',avgtime='9999999',plotfile=str(bpcal)+'-Df-CORRECTED.png',showgui=False,overwrite=True)


'''


# Calibrate Secondary -p  and T - amplitude normalized to 1
gaincal(vis = calms, caltable = gtab_sec_p, selectdata = True,\
    solint = "inf", field = gcal, combine = "",refantmode='strict',\
    refant = ref_ant, gaintype = "G", calmode = "p",uvrange='>150lambda',\
    gaintable = [ktab, gtab_a,btab,ptab_df])

gaincal(vis = calms, caltable = Ttab_sec, selectdata = True,\
    solint = "inf", field = gcal, combine = "",refantmode='strict',\
    refant = ref_ant, gaintype = "T", calmode = "ap",uvrange='>150lambda',\
    solnorm=True, gaintable = [ktab, gtab_sec_p,gtab_a,btab,ptab_df])


applycal(vis=calms, field=gcal, gaintable=[ktab, gtab_sec_p,gtab_a,btab,Ttab_sec,ptab_df])

# Check calibration of secondary
if do_plot ==True:
    os.system("shadems --xaxis UV  --yaxis CORRECTED_DATA --field "+ gcal_id+" --corr XX,YY --png './PLOTS/Gcal-amp-XX-YY.png' "+calms)
    os.system("shadems --xaxis UV  --yaxis CORRECTED_DATA:phase --field "+ gcal_id+" --corr XX,YY --png './PLOTS/Gcal-phase-XX-YY.png' "+calms)

# TO ADD: selfcal on secondary to improve phase


#apply calibration up to  now to xcal: XY and YX will vary with time due to pang, CHECK that power of XY,YX applitude is not close to 0 (not power to cailbrate
#plotms(vis='moon_uhf_calibrators.ms', xaxis='time', yaxis='amplitude', xdatacolumn='corrected', ydatacolumn='corrected', correlation='XY,YX', coloraxis='corr', uvrange=">1m", avgchannel='9999999',  field='J1331+3030')

applycal(vis=calms,field=xcal,gaintable=[ktab,gtab_p,gtab_a,btab,Ttab_sec,ptab_df])
if do_plot ==True:
     os.system("shadems --xaxis CORRECTED_DATA:phase  --yaxis CORRECTED_DATA:amp --field "+ xcal_id+" --corr XX,YY --png './PLOTS/Xf-precalXf-XX-YY.png' "+calms)
     os.system("shadems --xaxis TIME  --yaxis CORRECTED_DATA:amp --field "+ xcal_id+" --corr XY,YX --png './PLOTS/Xf-precalXf-XY-YX.png' "+calms)

# Calibrate XY phase: calibrate P on 3C286 - refine the phase
gaincal(vis = calms, caltable = gtab_pol_p, selectdata = True,\
        solint = "inf", field = xcal, combine = "",scan='',refantmode='strict',\
    refant = ref_ant, gaintype = "G", calmode = "p",uvrange='',\
        gaintable = [ktab, gtab_a,btab,ptab_df], parang = False)

#apply calibration up to  now, including phase refinement to xcal - corsshands shoudl be real vaue dominated, imaginary willl give idea of induced elliptcity. change in real axis due to parang
applycal(vis=calms,field=xcal,gaintable=[ktab,gtab_pol_p,gtab_a,btab,Ttab_sec,ptab_df])


if do_plot ==True:
     os.system("shadems --xaxis CORRECTED_DATA:phase  --yaxis CORRECTED_DATA:amp --field "+ xcal_id+" --corr XX,YY --png './PLOTS/Xf-precalXf-XX-YY-refinePhase.png' "+calms)
     os.system("shadems --xaxis TIME  --yaxis CORRECTED_DATA:amp --field "+ xcal_id+" --corr XY,YX --png './PLOTS/Xf-calXf-XY-YX-amp-time.png' "+calms)

#CHECK: from here Ttab is applied in applycal but not in the calls to gainca (Ben says ok, it is just a phase that we are deriving at Ttab is around 1 so  that should be fine)
     
#selfcal on Xcal - TO DO:larger FOV and mask, to further improve model
if selfcal_xcal==True:
    tclean(vis=calms,field=xcal,cell='0.5arcsec',imsize=512,niter=1000,imagename=xcal+'-selfcal',weighting='briggs',robust=-0.2,datacolumn= 'corrected',deconvolver= 'mtmfs',\
       nterms=2,specmode='mfs',interactive=False)
    gaincal(vis=calms,field=xcal, calmode='p', solint='30s',caltable=gtab_pol_p+'-selfcal',refantmode='strict',\
        refant=ref_ant,gaintype='G',gaintable = [ktab, gtab_a,btab,ptab_df], parang = False)
    gtab_pol_p=gtab_pol_p+"-selfcal"
     

# Cross-hand delay calibration - BEN says you can skip it - very sensitive to RFI
gaincal(vis = calms, caltable = kxtab, selectdata = True,\
            solint = "inf", field = xcal, combine = "scan", scan=scan_xcal,\
            refant = ref_ant, gaintype = "KCROSS",refantmode='strict',\
            gaintable = [ktab, gtab_pol_p, gtab_a, btab, ptab_df],\
            parang = True)


# Calibrate XY phase - combine scan to improve SNR - better add Ttab_sec
polcal(vis = calms, caltable = ptab_xf, selectdata = True,scan=scan_xcal,combine='scan',\
       solint = "inf,20MHz", field = xcal,uvrange='',\
       refant = ref_ant, poltype = "Xf",  gaintable = [ktab, gtab_pol_p, gtab_a,btab,ptab_df,kxtab ])
 
 


applycal(vis=calms, scan=scan_xcal, field=xcal,gaintable=[ktab, gtab_pol_p, gtab_a, btab, Ttab_sec, ptab_df, kxtab, ptab_xf],\
         parang=True)

# Check: plot imaginary versus real and compare to preious plot

if do_plot==True:
    os.system("shadems --xaxis CORRECTED_DATA:imag --field "+xcal_id+" --yaxis CORRECTED_DATA:real --corr XY,YX --png './PLOTS/Xf-calXf-XY-YX-real-im.png' "+calms)
    os.system("shadems --xaxis CORRECTED_DATA:phase  --yaxis CORRECTED_DATA:amp --field "+ xcal_id+" --corr XX,YY --png './PLOTS/Xf-calXf-XX-YY-refinePhase.png' "+calms)


if split_xcal ==True:

    split(vis=calms,scan=scan_xcal,field=xcal,outputvis=calms.replace('.MS','.'+str(xcal)+'-cal.MS'))



if apply_target==True:

    tb.open(targetms+'/FEED', nomodify=False)
    feed_angle = tb.getcol('RECEPTOR_ANGLE')
    new_feed_angle = np.zeros(feed_angle.shape)
    tb.putcol('RECEPTOR_ANGLE', new_feed_angle)
    tb.close()

    applycal(vis=targetms,gaintable=[ktab, gtab_sec_p, gtab_a, btab, Ttab_sec, ptab_df, kxtab, ptab_xf],parang=True)


# FOR SELFCAL: Either selfcal only for scalar phase ad amplitude from here OR do images and gaincal with parang=True becasue parag correction does not commune with gain amplitude
# Remember: Parang correction is amplitude correction, so if you selfcalon phase only tou can selfcal diagonal XX and YY separately

