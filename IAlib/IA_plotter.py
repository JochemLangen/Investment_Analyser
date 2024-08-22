import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import norm

from IA_stats import *

class plotter(stats):
    script_location = os.path.realpath(__file__)
    
    def __init__(self, fontsize=15, tickwidth=2, ticklength=4):
        self.fontsize = fontsize
        self.tickwidth = tickwidth
        self.ticklength = ticklength
        return
    
    def future_plot(self, std_array, std_err, return_mat, time, std_mult, \
                    limit_mult, time_index=-1):
        
        std_mult = np.asarray(std_mult)
        
        #Cumulative return
        fig = plt.figure()
        
        ax1 = fig.add_axes((0,0,1,1))
        self.__generate_plot(ax1, std_array, std_err, time, std_mult, limit_mult, \
                             ylabel='Cum. Relative Return (%)', xlabel=None)
        
        #Annual return
        ax2 = fig.add_axes((0,-1.05,1,1))
        self.__generate_plot(ax2, std_array[:,2:], std_err[:,2:], \
                             time, std_mult, limit_mult, ylabel='Avg. Annualised Relative Return (%)')
        
        ax3 = fig.add_axes((1.15, -0.525, 1, 1))
        self.__distr_plot(ax3, return_mat, std_mult, time_index)
            
        fig.show()
        
        return
    
    def __generate_plot(self, ax, std_array, std_err, time, std_mult, limit_mult, \
                        scale=None, ylabel='Return (%)', xlabel='Time (months)'):
        
        ax.plot(time, np.zeros_like(time), color='gray', linestyle=':')
        colour_base = 0.3
        colours = (1 - colour_base) * std_mult/max(std_mult)
        colour_max_i = len(colours)-1
        
        #Positive std lines
        for index, stdi in enumerate(std_mult[::-1]):
            pos_colour = [0, colours[colour_max_i-index], colours[colour_max_i-index]]
            ax.plot(time, std_array[:,0] + stdi * std_array[:,1], linestyle = '--', \
                    color = pos_colour, marker='x', label='m + {}s'.format(stdi))
        #Main line
        ax.plot(time, std_array[:,0], color='black', marker='x', label = 'mean')
        
        
        #Negative std lines
        for index, stdi in enumerate(std_mult):
            neg_colour = [colours[index], 0, colours[index]]
            ax.plot(time, std_array[:,0] - stdi * std_array[:,1], linestyle = '--', \
                    color=neg_colour, marker='x', label='m - {}s'.format(stdi))
        
        ax.legend()
        lim_max = max(std_array[:,0] + limit_mult * std_array[:,1])
        lim_min = max([-100, min(std_array[:,0] - limit_mult * std_array[:,1])])
        plt.ylim([lim_min, lim_max])
        plt.xlim([time[0], time[-1]])
        if scale == 'log':
            plt.xscale("log")
        
        plt.ylabel(ylabel,fontsize=self.fontsize)
                    
        ax.tick_params(left=True, right=True, labelleft=True, labelright=True)
        plt.yticks(fontsize=self.fontsize)
        plt.tick_params(axis='both', which='major', width= self.tickwidth, length= self.ticklength)
        plt.minorticks_on()
        plt.tick_params(axis='both', which='minor', width= self.tickwidth*2/3, length= self.ticklength/2)
        plt.tick_params(axis='both', which='both', left=True, right=True)
        
        if xlabel == None:
            ax.xaxis.tick_top()
        else:
            plt.xlabel(xlabel,fontsize=self.fontsize)

        plt.xticks(fontsize=self.fontsize)

        return
    
    def __distr_plot(self, ax, y_mat, std_mult, time_index):
        
        y_series = np.sort(y_mat[time_index])
        y_series = y_series[~np.isnan(y_series)]
        y_len = len(y_series)
        
        y_mean = np.mean(y_series)
        y_std = np.std(y_series, ddof=1)
        
        #Plot the histogram
        #The Freedman-Diaconis rule is used to obtain the bin width:    
        #Note, assumption of using int works approx for y_len being large enough,
        #Otherwise, interpolation between points should be used
        inter_qrt_range = y_series[int(y_len*3/4)] - y_series[int(y_len/4)]
        bin_width = 2*inter_qrt_range/np.cbrt(y_len)
        abs_max = np.max(abs(y_series - y_mean)) + bin_width
        bin_lim = np.array([y_mean - abs_max, y_mean + abs_max])
        bin_no = int(2*abs_max / bin_width)
        
        ax.hist(y_series,bins=bin_no,range=[bin_lim[0],bin_lim[1]],density=True)
        
        #Plot normal distr.
        return_arr = np.linspace(bin_lim[0], bin_lim[1], 100)
        prob_arr = norm.pdf(return_arr, y_mean, y_std)
        
        ax.plot(return_arr, prob_arr, linestyle='--', color='black')
        
        plt.ylim(bin_lim)
        plt.ylabel("Normalised probability density",fontsize=self.fontsize)
        plt.xlabel("Relative return (%)",fontsize=self.fontsize)
        ax.yaxis.set_label_position("right")
        
        ax.tick_params(axis='both', which='major', width= self.tickwidth, length= self.ticklength)
        ax.minorticks_on()
        ax.tick_params(axis='both', which='minor', width= self.tickwidth*2/3, length= self.ticklength/2)
        ax.tick_params(left=False, right=True, labelleft=False, labelright=True)
        plt.xticks(fontsize=self.fontsize)
        plt.yticks(fontsize=self.fontsize)


        return
    
    def full_plot(self):
        #Will also include historic data of the portfolio
        return
    
    