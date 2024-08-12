# Description:
import pandas as pd
import numpy as np
import os

class security:
    script_location = os.path.realpath(__file__)
    
    def __init__(self, fpath):
        # Extract the file extension
        file_ext = os.path.splitext(fpath)[1]
        
        # Check the file type (data source -> determines how it should be handled)
        if fpath.find('iShares') != -1 and file_ext == '.xlsx':
            
            #Read the excel file:
            excel = pd.read_excel(fpath, sheet_name= [1, 2], header=None) 
            
            self.name = excel[1][0][0] #Name of the security
            self.inception = excel[1][1][6] #Inception data
            self.inception_tick = self.__convert_time(np.asarray([self.inception]), 
                                                      time_form='iShares')
            self.type = excel[1][1][10]
            self.benchmark = excel[1][1][11]
            self.currency = excel[1][1][8]
            
            self.tick_time = self.__convert_time(np.asarray(excel[2][0][1:]),
                                                 time_form='iShares')
            self.return_matrix
            
            
        elif fpath.find('iShares') != -1 and file_ext == '.xls': 
            raise ValueError("The .xls file should be converted to a .xlsx file first. \n" +
                             "Use the data loader to do this.")  
        else:
            raise ValueError("The following data file has been found but is not supported: \n" + 
                             fpath + "\n" + "If this file type should be supported, implement it in: \n" +
                             self.script_location + "\n\nCurrently, the only supported files are: \n" + 
                             "'iShares*.xls'\n'iShares*.xlsx'")
        return

    def __convert_time(self, time_array, time_form='iShares'):
        # time_array needs to be a numpy array
        # could implement input parser
        
        # Zero point after which to start counting (at 1953 01 Jan, tick = 1)
        # This must be a leap year
        zero_point = 1952
        
        if time_form == 'iShares':
            
            # Array with conversion of month with corresponding ticks, the first row is
            # for a normal year, the second for a leap year (Sept is not included)
            month_ticks = np.array([[31, 59, 90, 120, 151, 181, 212, 243, 304, 334, 365],
                                   [31, 60, 91, 121, 152, 182, 213, 244, 305, 335, 366]])
            
            # The abbrev. of the months used in the iShares files (Sept not included as it 
            # is inconsistent with the others)
            month_list = np.array(['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug',
                                   'Oct', 'Nov', 'Dec'])
            
            # Function to convert from the month abbrev. to the corresponding tick number
            month_conv = lambda x:  month_ticks[0,x[3:6] == month_list] \
                                            if int(x[7:])%4 \
                                            else month_ticks[1,x[3:6] == month_list]
                                            
            # Function to convert Sept to the tick number for the leap and non-leap years
            month_conv_sep = lambda x: np.asarray([273]) if int(x[8:])%4 else np.asarray([274])
                                            
            # Function calculating the number of ticks for a given year, multiple of groups of 4 years
            # (i.e. one loop of the leap-year cycle) plus the remaining non-leap years
            year_conv = lambda x, y_ind: ((int(x[y_ind:])-zero_point)//4)*1461 \
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