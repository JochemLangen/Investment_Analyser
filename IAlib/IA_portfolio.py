import numpy as np
import os
import pandas as pd

from IA_data_loader import *
from IA_security import *
from IA_plotter import *

class portfolio(plotter, data_loader):
    script_location = os.path.realpath(__file__)
    
    def __init__(self, folder_location = os.path.realpath(\
            os.path.join(os.path.dirname(os.path.realpath(__file__)),\
                                                      '..', 'data', 'data.xlsx'))):
        plotter.__init__(self)
        data_loader.__init__(self)
        
        self.dataframe = pd.read_excel(folder_location)
        
        #Load all the securities from the data folder into a dictionary
        self.security_dict = {}        
        self.perform_task(self.dataframe['Name'], 'load_security')
        
        self.months = self.security_dict[self.dataframe['Name'][0]].months
        
        return
    
    def load_security(self, security_name):
        index = self.dataframe['Name'][self.dataframe['Name'] == security_name].index[0]
        
        filepath = os.path.join(self.folder, self.dataframe['Security_loc'][index])
        
        self.security_dict[security_name] = security(filepath)
        return
    
    def plot_portfolio(self, coef_type='Fitted_coef', std_mult=[1,2,3], limit=2, time_index=-1):
        #Plot the portfolio
        
        #Generate the input list to pass to calc_std_2D
        input_list = [self.months]
        for index, element in enumerate(list(self.security_dict.keys())):
            input_list += [self.security_dict[element].return_matrix, \
                           self.dataframe[coef_type][index]]
                
        #Calculate potfolio statistics
        self.std_array, self.std_err, self.return_matrix = self.calc_std_2D(*input_list)
        
        #Generate plot
        self.future_plot(self.std_array, self.std_err, self.return_matrix, \
                         self.months, std_mult, limit, time_index=time_index)
        
        return
        
    def fetch_data(self):
        #Use data loader to download and clean the latest data
        #Update the data.xlsx sheet with the latest names
        
        return
      
    def optimise(self):
        #Find the most optimised portfolio, given input on priorities
        return