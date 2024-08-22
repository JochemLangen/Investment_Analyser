import pandas as pd
import numpy as np
import os
from scipy.interpolate import PchipInterpolator

from IA_plotter import *

class security(plotter):
    script_location = os.path.realpath(__file__)
    
    # Zero point after which to start counting (at 1953 01 Jan, tick = 1)
    # This must be a leap year
    zero_point = 1952
    
    def __init__(self, fpath, months=None):
        super().__init__()
        
        self.__extract_file(fpath)
        
        time_intervals = self.generate_intervals(months)
        
        self.return_matrix = self.calc_return_matrix(self.tick_time, \
                                                     self.return_series, time_intervals)
        return
    
    def __extract_file(self, fpath):
        
        ## Extract the data
        # Extract the file extension
        file_ext = os.path.splitext(fpath)[1]
        
        # Check the file type (data source -> determines how it should be handled)
        if fpath.find('iShares') != -1 and file_ext == '.xlsx':
            
            #Read the excel file:
            excel = pd.read_excel(fpath, sheet_name= [1, 2], header=None) 
            
            self.name = excel[1][0][0] #Name of the security
            self.inception = excel[1][1][6] #Inception data
            self.inception_tick = self.convert_time(np.asarray([self.inception]), 
                                                      time_form='iShares')[0]
            self.type = excel[1][1][10]
            self.benchmark = excel[1][1][11]
            self.currency = excel[1][1][8]
            
            orig_tick_time = self.convert_time(np.asarray(excel[2][0][1:]),
                                                 time_form='iShares')
            orig_return = excel[2][5][1:]
            
            # Remove entries with '--' and reverse order (from start to now)
            numeric_entries = ~orig_return.str.contains("-", na=False)
            orig_tick_time = orig_tick_time[numeric_entries][::-1]
            orig_return = orig_return[numeric_entries][::-1]
            
            # Turn array into float
            orig_return = np.asarray(orig_return, dtype=float)
            
            
        elif fpath.find('iShares') != -1 and file_ext == '.xls': 
            raise ValueError("The .xls file should be converted to a .xlsx file first. \n" +
                             "Use the data loader to do this.")  
        else:
            raise ValueError("The following data file has been found but is not supported: \n" + 
                             fpath + "\n" + "If this file type should be supported, implement it in: \n" +
                             self.script_location + "\n\nCurrently, the only supported files are: \n" + 
                             "'iShares*.xls'\n'iShares*.xlsx'")
        
            
    	## Interpolate data to full dataset 
        #(interpolation is done so the return can be calculated on all data and sampling
        # biases are removed)
        self.tick_time = np.arange(orig_tick_time[0], orig_tick_time[-1], 1)
        # Perform interpolation (pchip is used for most accurate interpolation, without overshooting)
        self.return_series = PchipInterpolator(orig_tick_time, orig_return)(self.tick_time)
        
        return
    
    def convert_time(self, time_array, time_form='iShares'):
        # time_array needs to be a numpy array
        # could implement input parser
        
        if time_form == 'iShares':
            
            # Array with conversion of month with corresponding ticks from the previous months, 
            # the first row is for a normal year, the second for a leap year (Sept is not included)
            month_ticks = np.array([[0, 31, 59, 90, 120, 151, 181, 212, 273, 304, 334],
                                   [0, 31, 60, 91, 121, 152, 182, 213, 274, 305, 335]])
            
            # The abbrev. of the months used in the iShares files (Sept not included as it 
            # is inconsistent with the others)
            month_list = np.array(['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug',
                                   'Oct', 'Nov', 'Dec'])
            
            # Function to convert from the month abbrev. to the corresponding tick number
            month_conv = lambda x:  month_ticks[0,x[3:6] == month_list] \
                                            if int(x[7:])%4 \
                                            else month_ticks[1,x[3:6] == month_list]
                                            
            # Function to convert Sept to the tick number for the leap and non-leap years
            month_conv_sep = lambda x: np.asarray([243]) if int(x[8:])%4 else np.asarray([244])
                                            
            # Function calculating the number of ticks for a given year, multiple of groups of 4 years
            # (i.e. one loop of the leap-year cycle) plus the remaining non-leap years
            year_conv = lambda x, y_ind: ((int(x[y_ind:])-self.zero_point)//4)*1461 \
                                         + (int(x[y_ind:])%4)*365
                                         
            # Combining the functions above, to add the days, months and years and loop through all entries
            tick_time = np.asarray([int(date[:2]) + \
                           (year_conv(date, 8) + month_conv_sep(date) \
                           if date[3:7] == 'Sept' \
                           else year_conv(date, 7) + month_conv(date)) \
                           for date in time_array], dtype=int)[:,0]
                
        
        else:
            raise ValueError("The provided time_form is not supported: {}\n".format(time_form))
        return tick_time
    
    def generate_intervals(self, months=None):
        
        #Set a default array with the month intervals to use
        if months == None:
            yrs = 5
            self.months = np.append(np.arange(1,12,1, dtype=int), np.arange(12, yrs*12, 6, dtype=int))
        else:
            self.months = months
        
        #Return the calculated intervals, using the average month length in a year
        return np.asarray(self.months*365.25/12, dtype=int)
    
    def calc_return_matrix(self, t, y, t_int):
        
        int_len = len(t_int)
        t_len = len(t)
        
        # Extract indices from the ticks:
        indices = t - t[0]
        index_mx = np.tile(indices, (int_len, 1)) #Convert into matrix
        index_mx += np.tile(t_int, (t_len,1)).T #Add time intervals to matrix

        #Setting too large indices to mask
        mask = index_mx > t_len-1
        index_mx[mask] = 0
        
        #Creating the y matrix based on the index matrix
        y_mx = y[index_mx]
        y_mx[mask] = np.nan

        #Calculate the deltas (the returns)        
        dy_mx = y_mx - np.tile(y, (int_len, 1))
        rel_dy_mx = dy_mx/y_mx
        
        return rel_dy_mx
    
    def plot_security(self, std_mult=[1,2,3],limit=2):
        
        self.std_array, self.std_err = self.calc_std_1D(self.return_matrix, self.months)
        
        self.future_plot(self.std_array, self.std_err, self.return_matrix*100, self.months, std_mult, limit)
        
        return