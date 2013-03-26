#!/usr/bin/env python
# 
# Copyright 2013 <+YOU OR YOUR COMPANY+>.
# 
# This is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
# any later version.
# 
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this software; see the file COPYING.  If not, write to
# the Free Software Foundation, Inc., 51 Franklin Street,
# Boston, MA 02110-1301, USA.
# 

import numpy as np
import pylab as pl
from gnuradio import gr

        
class freq_sync_py(gr.basic_block):
    """
    Perform frequency synchronization by correlating with the three continuous sine pilots
    """
    def __init__(self, rx):
        gr.basic_block.__init__(self,
            name="freq_sync_py",
            in_sig=[np.complex64],
            out_sig=[np.complex64])

        self.rx = rx
        self.FS = 48000
        self.nfft = 3200 # 3200 points result in a spectral resolution of 15 Hz --> pilot frequencies can be represented without error
        self.nfft        
        # TODO: interpolate the frequency pilot vector to a power of two length to reduce FFT size and computational load        
        self.nsamp_sym = 1280  
        self.delta_f = self.FS / self.nfft
        self.f_pil_index = np.array([np.round(750/self.delta_f), np.round(2250/self.delta_f), np.round(3000/self.delta_f)], dtype=int)
        #self.f_pil = np.zeros((f_pil_index[2]+1,), dtype=np.complex64)
        #self.f_pil[f_pil_index] = 10
        self.buf_ctr = 0
        self.buf_ctr_max = 15 # one frame equals 15 symbols in RM B
        self.buffer_filled = False
        self.fft_vec = np.zeros((self.buf_ctr_max, self.nfft))    
        self.fft_vec_avg = np.zeros((1, self.nfft))
        self.corr_vec = np.zeros((self.nfft, ))
        self.freq_offset = 0
        

    def forecast(self, noutput_items, ninput_items_required):
        #setup size of input_items[i] for work call
        for i in range(len(ninput_items_required)):
            ninput_items_required[i] = self.nfft
            
    def calc_avg_fft(self, in0):
        fft_tmp = np.fft.fft(in0[0:self.nfft], self.nfft)
        fft_tmp = np.fft.fftshift(fft_tmp)
        fft_tmp *= np.conj(fft_tmp) # square it for power spectrum density
        self.fft_vec[self.buf_ctr][:] = abs(fft_tmp)
        self.buf_ctr = (self.buf_ctr + 1) % self.buf_ctr_max
        # average FFT to get a better estimate of the spectrum
        self.fft_vec_avg = np.mean(self.fft_vec, 0)
        
    def pilot_corr(self):
        # add the FFT bins corresponding to the pilot positions for each shift and take the magnitude
#        self.fft_vec_avg = np.zeros((self.nfft,), dtype=np.complex64)
#        offset = 3200
#        self.fft_vec_avg[self.f_pil_index[0] + offset] = 1
#        self.fft_vec_avg[self.f_pil_index[1] + offset] = 1
#        self.fft_vec_avg[self.f_pil_index[2] + offset] = 1
        fft_vec_expanded = np.concatenate((self.fft_vec_avg, self.fft_vec_avg[:self.f_pil_index[2]]), axis=0)
        for i in range(self.nfft): 
            self.corr_vec[i] = abs(fft_vec_expanded[i+self.f_pil_index[0]] \
            + fft_vec_expanded[i+self.f_pil_index[1]] \
            + fft_vec_expanded[i+self.f_pil_index[2]])
                       
    def find_freq_offset(self):
        # find maximum and corresponding value
        peak_index = 0;
        peak_val = 0;
        for k in range(len(self.corr_vec)):
    		if self.corr_vec[k] > peak_val: 
    			peak_val = self.corr_vec[k]
    			peak_index = k	
       
        # wrap indices around because of fftshift
        peak_index -= self.nfft/2 
        self.freq_offset = peak_index * self.delta_f
        print "frequency offset: ",self.freq_offset, "Hz"
        
    def correct_freq_offset(self, in0):
        arg = -2*np.pi*self.freq_offset/self.FS # -2*pi*f*1/FS; -1 because we want to compensate the offset
        for i in range(self.nfft):
            in0[i] *= (np.cos(arg*i) + 1j*np.sin(arg*i)) # exp(j*2*pi*f*t)
        return in0[:self.nfft]
    
    def debug_plot(self):
        pl.subplot(311)
        pl.plot(self.corr_vec/max(self.corr_vec))
        pl.ylabel("correlation")
        pl.subplot(312)
        pl.plot(self.fft_vec_avg)
        pl.ylabel("avg fft")
        pl.subplot(313)
        pl.plot(self.fft_vec[abs(self.buf_ctr-1)])
        pl.ylabel("current fft")
        pl.show()
        
    def general_work(self, input_items, output_items):
        in0 = input_items[0]
        out = output_items[0]
        
        if len(in0) < self.nfft:
            print "not enough samples, skip work()"
            return 0
        else:
            # compute averaged FFT of input signal
            self.calc_avg_fft(in0[:self.nfft])
            if self.buf_ctr >= self.buf_ctr_max - 1: # the flag is never set back to false once the buffer is filled
                self.buffer_filled = True
                    
        if self.buffer_filled:
            self.pilot_corr()            
            self.find_freq_offset()
            out[:self.nfft] = self.correct_freq_offset(in0[:self.nfft]) 
            self.consume_each(self.nfft)
            return self.nfft

        else:
            print "freq_sync_py: filling buffer", self.buf_ctr, "/", self.buf_ctr_max
            self.consume_each(self.nfft)
            return 0
        
        
        
