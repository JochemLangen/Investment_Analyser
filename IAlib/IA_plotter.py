import numpy as np
import matplotlib.pyplot as plt
# from scipy.stats import norm
import scipy.stats

from IA_stats import *

class plotter(stats):
    script_location = os.path.realpath(__file__)
    
    def __init__(self, fontsize=15, tickwidth=2, ticklength=4):
        self.fontsize = fontsize
        self.tickwidth = tickwidth
        self.ticklength = ticklength
        return
    
    def future_plot(self, std_array, std_err, return_mat, time, title_input, std_mult, \
                    limit_mult, time_index=-1):
        
        std_mult = np.asarray(std_mult)
        
        #Cumulative return
        fig = plt.figure()
        
        ax1 = fig.add_axes((0,0,1,1))
        plt.title(title_input, fontsize=self.fontsize, loc='left')
                  
        self.__generate_plot(ax1, std_array, std_err, time, std_mult, limit_mult, \
                             ylabel='Cum. Relative Return (%)', xlabel=None)
        
        #Annual return
        ax2 = fig.add_axes((0,-1.15,1,1))
        self.__generate_plot(ax2, std_array[:,2:], std_err[:,2:], \
                             time, std_mult, limit_mult, ylabel='Avg. Annualised Relative Return (%)')
        plt.title('Avg. Annualised Relative Return at {} months: {}%'.format(\
                     time[time_index], round(std_array[time_index, 2],2)), fontsize=self.fontsize)
        
        ax3 = fig.add_axes((1.15, -0.525, 1, 1))
        self.__distr_plot(ax3, return_mat, std_mult, time, time_index)
            
        # fig.show()
        
        return
    
    def __generate_plot(self, ax, std_array, std_err, time, std_mult, limit_mult, \
                        scale=None, ylabel='Return (%)', xlabel='Time (months)'):
        
        ax.plot(time, np.zeros_like(time), color='gray', linestyle=':')
        colour_base = 0.3
        colours = (1 - colour_base) * std_mult/max(std_mult)
        colour_max_i = len(colours)-1
        
        #Calculate errors:
        err = np.empty((np.shape(std_array)[0], len(std_mult)))
        for index, stdi in enumerate(std_mult):
            err[:,index] = np.sqrt(std_err[:,0]**2 + (stdi*std_err[:,1])**2)
            
        #Positive std lines
        for index, stdi in enumerate(std_mult[::-1]):
            pos_colour = [0, colours[colour_max_i-index], colours[colour_max_i-index]]
            ax.errorbar(time, std_array[:,0] + stdi * std_array[:,1], yerr=err[:,-index-1],\
                        linestyle = '--', color = pos_colour, marker='x', label='m + {}s'.format(stdi))
        #Main line
        ax.errorbar(time, std_array[:,0], yerr=std_err[:,0], color='black', marker='x', label = 'mean')
        
        
        #Negative std lines
        for index, stdi in enumerate(std_mult):
            neg_colour = [colours[index], 0, colours[index]]
            ax.errorbar(time, std_array[:,0] - stdi * std_array[:,1], yerr=err[:,index],\
                        linestyle = '--', color = neg_colour, marker='x', label='m - {}s'.format(stdi))
        
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
    
    def __distr_plot(self, ax, y_mat, std_mult, time, time_index):
        
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
        
        ax.hist(y_series,bins=bin_no,range=[bin_lim[0],bin_lim[1]],density=True, zorder=30)
        
        #Plot probability lines
        ylimits = ax.get_ylim()
        std_mult_arr = np.append(np.append(std_mult[::-1], 0), -std_mult)
        txt_y_pos = ylimits[1]
        ylim = [ylimits[0], ylimits[1] * 11/10] #To provide space for the text
        
        for index, stdi in enumerate(std_mult_arr):
            x_pos = y_mean + stdi * y_std
            ax.plot([x_pos, x_pos], ylim, linestyle=':', color='black', zorder=index)

            #Print corresponding percentage
            nearest_index = np.argmin(abs(y_series - x_pos))
            if y_series[nearest_index] > x_pos: #Looking at percentage of points included below, 
            #so if the value is below the nearest index point, it will be one lower
            #y_len is already +1 compared to the indices so for val < x_pos, nothing is added
                percentage = np.round((nearest_index+1)/y_len * 100, decimals=1)
            else:
                percentage = np.round(nearest_index/y_len * 100, decimals=1)
                
            if stdi < 0:
                plt.text(x_pos+bin_width/2, txt_y_pos,\
                         "m - {}s\n={}%".format(-stdi, percentage), zorder=32)
            elif stdi > 0:
                plt.text(x_pos+bin_width/2, txt_y_pos,\
                         "m + {}s\n={}%".format(stdi, percentage), zorder=32)
            else:
                plt.text(x_pos+bin_width/2, txt_y_pos,\
                         "mean\n={}%".format(percentage), zorder=32)
        
        #Plot normal distr.
        xlimits = ax.get_xlim()
        return_arr = np.linspace(xlimits[0], xlimits[1], 100)
        prob_arr = scipy.stats.truncnorm.pdf(return_arr, (-100 - y_mean)/y_std, np.inf, loc=y_mean, scale=y_std)
        
        ax.plot(return_arr, prob_arr, linestyle='--', color='black', zorder=31)

        if y_mean + (std_mult[-1]+1) * y_std > bin_lim[1]:
            plt.xlim([y_mean - std_mult[-1] * y_std - bin_width,\
                      y_mean + (std_mult[-1]+1) * y_std]) #Extra space because of text
        else:
            plt.xlim(bin_lim)
            
        plt.ylim(ylim)
        plt.ylabel("Normalised Probability Density",fontsize=self.fontsize)
        plt.xlabel("Cumulative Relative Return (%)",fontsize=self.fontsize)
        ax.yaxis.set_label_position("right")
        
        ax.tick_params(which='both', left=False, right=True, labelleft=False, labelright=True)
        ax.tick_params(axis='both', which='major', width= self.tickwidth, length= self.ticklength)
        ax.minorticks_on()
        ax.tick_params(axis='both', which='minor', width= self.tickwidth*2/3, length= self.ticklength/2)
        plt.xticks(fontsize=self.fontsize)
        plt.yticks(fontsize=self.fontsize)
        plt.title('Return distribution at {} months'.format(time[time_index]),\
                  fontsize=self.fontsize)


        return
    
    def full_plot(self):
        #Will also include historic data of the portfolio
        return
    
    
    def plot_backtracing(self, ):
        ## Plotting        
        offset = 0
        range_lim = [offset+14500,offset+16000]
        
        fig = plt.figure()
        # plt.plot(t_old, y_old, label='index')
        plt.plot(new_t[range_lim[0]:range_lim[1]], fitted_y[range_lim[0]:range_lim[1]], label='fitted')
        # plt.plot(t_old, fitted_y, label='fitted')

        plt.plot(t[offset:offset+1300], y[offset:offset+1300], label='orig')
        plt.plot(new_t[range_lim[0]:range_lim[1]], smooth_y[range_lim[0]:range_lim[1]], label='final data')
        plt.legend()
        plt.show()
        
        fig = plt.figure()
        # plt.plot(t_old, y_old, label='index')
        plt.plot(t_old[:-1][-y_len:], fitted_y[-y_len:], label='fitted')
        # plt.plot(t_old, fitted_y, label='fitted')

        plt.plot(t, y, label='orig')
        plt.yscale('log')
        plt.legend()
        plt.show()
        
        
        plt.figure()
        plt.plot(t_old[1:], (fitted_y / y_n_factor) / (y_old[1:] / y_old_n_factor))
        plt.show()
        
        plt.figure()
        plt.plot(t_old[1:], fitted_y)
        plt.plot(t_old[1:], y_old[1:] / y_old_n_factor * y_n_factor)
        plt.plot(t, y, label='orig')
        plt.yscale('log')
        plt.show()
        
        
        
        plt.figure()
        plt.scatter(y_old_norm[1:], fitted_y[-y_len:]/y_n_factor, marker='.')
        plt.scatter(y_old_norm[1:], y_norm, marker='.')
        plt.ylabel('Y norm')
        plt.xlabel('Y index norm')
        plt.show()
        
        
        plt.figure()
        plt.plot(t, y_resid/y)
        plt.ylim([-0.1,0.1])
        plt.show()
        
        return
        
    
    