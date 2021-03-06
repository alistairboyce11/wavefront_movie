'''
This script contains the function used to generate synthetic seismogram

generate_seismogram(epi_dist=90,evtdepth=0,time_window=3600,norm_wave=False,filter_params=[fmin, fmax],out_loc='../wavefront_movie_outputs/'):
    Given a bunch of input parameters, use instaseis to make synthetic seismogram.

'''


### Importing various python libraries
# numpy is a useful toolkit for scientific computations
import numpy as np
# matplotlib is a plotting toolkit
import matplotlib.pyplot as plt
# Obspy is a seismic toolkit
import obspy
import obspy.signal.rotate
from obspy import UTCDateTime
import obspy.geodetics.base
import obspy.geodetics
from obspy.taup import TauPyModel
from obspy.taup import plot_travel_times
from obspy.taup import plot_ray_paths

import matplotlib
from matplotlib.animation import FuncAnimation
# More about the obspy routines we are using can be found here:
# https://docs.obspy.org/packages/obspy.taup.html

# more imports
import instaseis
from obspy import read
import sys,glob
import os.path
from IPython.display import HTML, Image
matplotlib.rc('animation', html='html5')

# velocity model as a function of depth.
model = TauPyModel(model='ak135')

##################################################################################

def generate_seismogram(epi_dist=90,evtdepth=0,time_window=3600,norm_wave=False,filter_params=[],out_loc='../wavefront_movie_outputs/'):
    # Given a bunch of input parameters, use instaseis to make synthetic seismogram.
    
    Rayleigh_vel = 4.2                                  # Assumed Rayleigh wavespeed in km/s
        
    # EQ and Receiver station latitude and longitude
    # Fix station longitude to be equivalent to epi_dist.
    evtlatitude=0
    evtlongitude=0
    stlatitude=0
    stlongitude=epi_dist
    
    File_Wave = out_loc+'synth_seis_'+ str(evtdepth)+'km_'+str(epi_dist)+'deg.PICKLE'
        
    # Load database with Green Functions
    # db = instaseis.open_db("syngine://prem_a_2s")
    # db = instaseis.open_db("syngine://ak135f_1s")
    db = instaseis.open_db("syngine://ak135f_2s ")
    EQ_time=UTCDateTime('2004-12-26 00:00:00')

    # Other option for source definition
    # source = instaseis.Source.from_strike_dip_rake(latitude=evtlatitude, longitude=evtlongitude, depth_in_m=evtdepth*1000, strike=60,dip=30, rake=90, M0=1E12, sliprate=1, dt=0.1, origin_time=EQ_time)
    source = instaseis.Source(latitude=evtlatitude, longitude=evtlongitude, depth_in_m=evtdepth*1000, m_rr = 1.0e+29, m_tt = 1.0e+29, m_pp = 1.0e+29, m_rt = 0, m_rp = 0, m_tp = 0, sliprate=1, dt=0.1, origin_time=EQ_time)

    # Station parameters
    receiver = instaseis.Receiver(latitude=stlatitude, longitude=stlongitude, network="AB",station="CDE", location="SY")

    # compute raypath statistics
    distm, az, baz = obspy.geodetics.base.gps2dist_azimuth(evtlatitude, evtlongitude, stlatitude, stlongitude)
    distdg = distm / (6371.e3 * np.pi / 180.)

    start = EQ_time
    end   = EQ_time+time_window 

    # Run function to get waveforms
    st = db.get_seismograms(source=source, receiver=receiver,kind='displacement', dt=0.1)
    # Add headers to Pickle in .stats
    st[0].stats['evla'] = evtlatitude
    st[0].stats['evlo'] = evtlongitude
    st[0].stats['evdp'] = evtdepth # want EQ depth in km in PICKLE (do not x1000)
    st[0].stats['stla'] = stlatitude
    st[0].stats['stlo'] = stlongitude
    st[0].stats['dist'] = distdg
    st[0].stats['az'] = az
    st[0].stats['baz'] = baz

    # Rotate synthetics to radial and transverse
    stE = st.select(channel='BXE')
    stN = st.select(channel='BXN')
    stZ = st.select(channel='BXZ')
    [stRtmp,stTtmp]=obspy.signal.rotate.rotate_ne_rt(stN[0].data,stE[0].data,st[0].stats['baz'])
    stR=stN[0].copy()
    stR.stats['channel']='BXR'
    stR.data = stRtmp
    stT=stN[0].copy()
    stT.stats['channel']='BXT'
    stT.data = stTtmp

    st+=stR
    st+=stT

    # Check if Rayleigh waves arrive at seismometer - taper/mute them out.

    # Distance divided by velocity, gives body wave window before Rayleigh wave arrival.
    Body_wave_window = (distm/1000) / Rayleigh_vel

    if Body_wave_window > time_window:
        # No Rayleigh waves on seismogram
        # just make sure seismogram is correct length
        print('No interfering Rayleigh phases predicted...')
        st.trim(starttime=start, endtime=end, pad=True, nearest_sample=True, fill_value=0)
    else:
        # Rayleigh waves may exist of seismogram so:
        # Cut to body_wave_window length, taper, pad to 
        print('Interfering Rayleigh phases predicted - muting...')
        body_wave_endtime = EQ_time + Body_wave_window
        st.trim(starttime=start, endtime=body_wave_endtime, pad=False)
        st.taper(max_percentage=0.15, type='cosine') # This is a fairly large taper but make it look smoother.
        st.trim(starttime=start, endtime=end, pad=True, nearest_sample=True, fill_value=0)


    # Normalize waveform amplitude for each trace
    if norm_wave:
        for channel in st:
            print(channel.stats['channel'])
            print(channel.stats['starttime'], channel.stats['endtime'])
            windowed=channel[np.where(channel.times() >= 0) and np.where(channel.times() <= time_window )]
            norm=np.max(np.abs(windowed))
            channel.data=channel.data/norm


    #OVERWRITES previous PICKLE with new synthetics

    if len(filter_params) > 0:
        fmin=filter_params[0] # e.g., 0.02
        fmax=filter_params[1] # e.g., 0.5
        print('Bandpass filtering with corners: '+str(fmin)+ ' - '+str(fmax))
        st.filter('bandpass', freqmin=fmin,freqmax=fmax, corners=2, zerophase=True)
        st.taper(max_length=5, max_percentage=0.02, type='cosine')

    st.write(File_Wave,format='PICKLE')  
    return


##################################################################################
    
def check_synth_seis(epi_dist=90,evtdepth=0,time_window=3600,out_loc='../wavefront_movie_outputs/'):
    # Checks if seismogram is present or needs generating, returns fp=True/False
    
    File_Wave = out_loc+'synth_seis_'+ str(evtdepth)+'km_'+str(epi_dist)+'deg.PICKLE'
    
    if os.path.exists(File_Wave):
        seis=read(File_Wave, format='PICKLE')
        if round(seis[0].stats['endtime']-seis[0].stats['starttime']) == time_window:
            print('File '+str(File_Wave)+ ' present :)\n')
            fp=True
        else:
            print('File '+str(File_Wave)+ ' incorrect length... :(\n')
            fp=False
    else:
        print('File '+str(File_Wave)+ ' missing... :(\n')
        fp=False

    return(fp)
    
##################################################################################
    
def load_synth_seis(epi_dist=90,evtdepth=0,out_loc='../wavefront_movie_outputs/'):
    # Loads synthetic seismogram into memory - vertical component.
    
    File_Wave = out_loc+'synth_seis_'+ str(evtdepth)+'km_'+str(epi_dist)+'deg.PICKLE'

    synth=read(File_Wave,format='PICKLE')
    # synth_BXZ=synth.select(channel='BXZ')
    
    # return the synthetic obspy.core.stream.Stream
    # the channel is now selected in the main script.
    return(synth)

