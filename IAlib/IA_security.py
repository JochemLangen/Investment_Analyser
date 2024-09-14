import pandas as pd
import numpy as np
import os
from scipy.interpolate import PchipInterpolator
import datetime
import pickle

from IA_plotter import *
from IA_fitter import *

class security(plotter, fitter):
    script_location = os.path.realpath(__file__)
    
    # Zero point after which to start counting (at 1953 01 Jan, tick = 1)
    # This must be a leap year
    zero_point = 1952
    
    def __init__(self, fpath, index_fpath=None, months=[], start_date=None, calc_ortho=True, calc_mat=True):
        #
        # start_date: format is dd/mm/yyyy. Minimum is 02/01/1970
        plotter.__init__(self)
            
        self.__extract_security(fpath)
        
        if index_fpath != None:
            self.__extract_index(index_fpath)
            
            self.security_tick_time = self.tick_time.copy()
            self.security_return_series = self.return_series.copy()
            
            self.return_series, self.tick_time, self.backtracing = \
                self.backtrace_data(self.return_series, self.index_return_series, \
                                self.tick_time, self.index_tick_time, calc_ortho=calc_ortho)
                    
        self.save_security()

        if calc_mat == True:
            self.return_matrix = self.calc_return_matrix(months, start_date)
        
        return

    
    def __extract_security(self, fpath):
        
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
            orig_return = excel[2][2][1:]
            
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
        self.tick_time = np.arange(orig_tick_time[0], orig_tick_time[-1], 1, dtype=int)
        # Perform interpolation (pchip is used for most accurate interpolation, without overshooting)
        self.return_series = PchipInterpolator(orig_tick_time, orig_return)(self.tick_time)
        
        return
    
    def __extract_index(self, fpath):
        
        ## Extract the data
        # Extract the file extension
        file_ext = os.path.splitext(fpath)[1]
        
        # Check the file type (data source -> determines how it should be handled)
        if fpath.find('yahoo') != -1 and file_ext == '.csv':
            # Read csv file
            Excel = pd.read_csv(fpath)

            if 'Date' in Excel.columns: #Old format, with download API:
                
                # Extract time
                datetime_series = pd.to_datetime(Excel['Date'][1:], format='%d/%m/%Y')
                
                timestamps = datetime_series.apply(lambda x: x.timestamp())
                
                # Extract return series
                orig_return = np.array(Excel['Adj Close'][1:])
                
            elif 'Timestamp' in Excel.columns: #New format from json data in chart
                timestamps = Excel['Timestamp'][1:]
                
                orig_return = np.array(Excel['Adj Close'][1:])
            else:
                raise ValueError("The following Yahoo data file has an unsupported format: \n" + 
                                 fpath + "\n" + "If this file type should be supported, implement it in: \n" +
                                 self.script_location)
            
            #Convert time to iShares format
            orig_tick_time = self.convert_time(np.array(timestamps), time_form='Yahoo')
            
            # Turn array into float
            orig_return = np.asarray(orig_return, dtype=float)
        else:
            raise ValueError("The following data file has been found but is not supported: \n" + 
                             fpath + "\n" + "If this file type should be supported, implement it in: \n" +
                             self.script_location + "\n\nCurrently, the only supported files are: \n" + 
                             "'*yahoo.csv'")
            
        ## Interpolate data to full dataset 
        #(interpolation is done so the return can be calculated on all data and sampling
        # biases are removed)
        self.index_tick_time = np.arange(orig_tick_time[0], orig_tick_time[-1], 1, dtype=int)
        # Perform interpolation (pchip is used for most accurate interpolation, without overshooting)
        self.index_return_series = PchipInterpolator(orig_tick_time, orig_return)(self.index_tick_time)
        
        return
    
    def convert_time(self, time_array, time_form='iShares'):
        # time_array needs to be a numpy array
        # could implement input parser

        
        if time_form == 'iShares':
            # dd/mm(m)/yyyy
            
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
                
        elif time_form == 'Yahoo':
            #Turn the datetime ticks into date ticks and add the offset to be consistent with iShares format
            datetime_ticks = np.empty_like(time_array, dtype=int)

            np.floor(time_array/86400, out=datetime_ticks, casting='unsafe')

            tick_time = datetime_ticks + self.convert_time(np.array(['01/Jan/1970']), time_form = 'iShares')
        else:
            raise ValueError("The provided time_form is not supported: {}\n".format(time_form))
        return tick_time
    
    def generate_intervals(self, months=[]):
        
        #Set a default array with the month intervals to use
        if np.shape(months)[0] == 0:
            yrs = 10
            self.months = np.append(np.arange(1,12,2, dtype=int), np.arange(12, yrs*12, 8, dtype=int))
        else:
            self.months = months
        
        #Return the calculated intervals, using the average month length in a year
        return np.asarray(self.months*365.25/12, dtype=int)
    
    def calc_return_matrix(self, months, start_date=None):
        
        t_int = self.generate_intervals(months)
        
        #Set the data start date:
        if start_date == None:
            self.start_tick = self.tick_time[0]
        else:
            #Convert string format start_date to tick with the zero_point
            tick_form_delta = self.convert_time(np.array(['01/Jan/1970']), time_form = 'iShares')
            self.start_tick = int(np.floor((datetime.datetime.strptime(start_date + ' 01', '%d/%m/%Y %H').timestamp())/86400) + tick_form_delta) 
                #Note, the hour needed to be added because of the timestamp datetime generates for a simple date
            
            #Slice the arrays to use the start_index
            start_index = np.argmin(abs(self.tick_time - self.start_tick))
            self.tick_time = self.tick_time[start_index:]
            self.return_series = self.return_series[start_index:]
        
        
        int_len = len(t_int)
        t_len = len(self.tick_time)
        
        # Extract indices from the ticks:
        indices = self.tick_time - self.tick_time[0] #As all points are a full set of integers from the start date to now
        index_mx = np.tile(indices, (int_len, 1)) #Convert into matrix
        index_mx += np.tile(t_int, (t_len,1)).T #Add time intervals to matrix
        
        #Setting too large indices to mask (at the end of the return series, you can't
        #calculate the delta anymore i.e. 1 month return 0.5 months before the end of the series).
        #The indices for these non-calculable points are set to zero for now and then set to nan after
        mask = index_mx > t_len-1
        index_mx[mask] = 0
        
        #Creating the y matrix based on the index matrix
        y_mx = self.return_series[index_mx]
        y_mx[mask] = np.nan

        #Calculate the deltas (the returns)   
        y_mat = np.tile(self.return_series, (int_len, 1))
        dy_mx = y_mx - y_mat
        rel_dy_mx = dy_mx/y_mat
        
        
        return rel_dy_mx
    
    def plot_security(self, std_mult=[1,2,3], limit=2, time_index=-1):
        
        #Calculate statistics
        self.std_array, self.std_err = self.calc_std_1D(self.return_matrix, self.months)
        
        #Convert starting tick to string:
        tick_form_delta = int(self.convert_time(np.array(['01/Jan/1970']), time_form = 'iShares'))
        start_date = datetime.datetime.fromtimestamp((self.start_tick-tick_form_delta)*86400).date()
        
        #Generate plots
        title = 'Return estimation from historic data ({}+): {}'.format(start_date, self.name)
        self.future_plot(self.std_array, self.std_err, self.return_matrix*100, \
                         self.months, title, std_mult, limit, time_index=time_index)
        
        return
    
    def save_security(self, saving_loc = os.path.realpath(\
            os.path.join(script_location,'..', '..', 'data', 'pickles'))):
        
        file_loc = os.path.join(saving_loc, self.name.replace(' ', '_')+'.pkl')
        
        with open(file_loc, 'wb') as file:
            pickle.dump(self, file, pickle.HIGHEST_PROTOCOL)
            
        return
            