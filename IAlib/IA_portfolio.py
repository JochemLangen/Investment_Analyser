import numpy as np
import os
import pandas as pd
import pickle

from IA_data_loader import *
from IA_security import *
from IA_plotter import *
from IA_fitter import *

class portfolio(plotter, data_loader, fitter):
    script_location = os.path.realpath(__file__)
    
    def __init__(self, data_location = os.path.realpath(\
            os.path.join(os.path.dirname(os.path.realpath(__file__)),\
                         '..', 'data', 'data.xlsx')), months = [], start_date=None, load=False):
        
        plotter.__init__(self)
        data_loader.__init__(self)
        
        self.dataframe = pd.read_excel(data_location)
        
        #Load all the securities from the data folder into a dictionary
        self.securities = {}        
        self.perform_task(self.dataframe['Name'], 'load_security', load)
        
        if load == False: #Otherwise the files are reloaded i.e. had been processed before so these names should already be good
            self.dataframe['Name'] = list(self.securities.keys())
            self.save_dataframe()
        
        #Calculate the return matrices per security:
        self.perform_task(self.dataframe['Name'], 'calc_return_matrix_per_security', \
                          months=months, start_date=start_date)
        
        self.months = self.securities[self.dataframe['Name'][0]].months
        
        return

    
    def plot_portfolio(self, coef_type='Fitted_coef', std_mult=[1,2,3], limit=2, time_index=-1, coeffs=None):
        #Plot the portfolio
        
        #Generate the input list to pass to calc_std_2D
        input_list = [self.months]
        
        if coeffs == None: #Use coeffs from dataframe
            for index, element in enumerate(list(self.securities.keys())):
                input_list += [self.securities[element].return_matrix, \
                               self.dataframe[coef_type][index]]
        else: #manual input of coeffs for this function
            for index, element in enumerate(list(self.securities.keys())):
                input_list += [self.securities[element].return_matrix, \
                               coeffs[index]]
                
        #Calculate potfolio statistics
        self.std_array, self.std_err, self.return_matrix = self.calc_std_2D(*input_list)
        
        #Generate plot
        self.future_plot(self.std_array, self.std_err, self.return_matrix, \
                         self.months, std_mult, limit, time_index=time_index)
        
        return
    
    def plot_securities(self, std_mult=[1,2,3], limit=2, time_index=-1):
        #Plot each individual security in the portfolio
        self.perform_task(list(self.securities.keys()), 'plot_indiv_security', \
                          std_mult=std_mult, limit=limit, time_index=time_index)            
        return
        
    def fetch_data(self, which='both'):
        #Use data loader to download and clean the latest data
        #Update the data.xlsx sheet with the latest names
        #
        #Note, it is assumed there is already a downloaded version of the security files present
        # but not for the index.
        
        
        ## Download index data:
        index_paths = np.empty_like(self.dataframe['Name'])
        index_filename = np.empty_like(index_paths)
        security_paths = np.empty_like(index_paths)
        
        for index, filename in enumerate(self.dataframe['Name']):
            index_filename[index] = filename.replace(' ', '_')
            index_paths[index] = os.path.realpath(os.path.join(self.folder, '..', 'index', index_filename[index]))
            
            #Converting the security file format to .xls (pre-cleaning state)
            security_filename = self.dataframe['Security_loc'][index]
            security_filename = security_filename[0:security_filename.rfind('.')] + '.xls'
            security_paths[index] = os.path.join(self.folder, security_filename)
        
        if which == 'indices' or which == 'both':
            #Download the index files     
            self.download_indices(self.dataframe['Index_down'], index_paths)
            
            #Add the new index filenames to the dataframe and save
            self.dataframe['Index_loc'] = index_filename
            self.save_dataframe()
        
        if which == 'securities' or which == 'both':
            #Download the security files (no specific securities wrapper is needed for iShares, they are
            #automatically up-to-date)
            self.perform_download(self.dataframe['Security_down'], security_paths, 'Securities')
            
            #Clean the iShares files
            self.clean_files()
        
        return
      
    def optimise(self):
        #Find the most optimised portfolio, given input on priorities
        return
    
    def save_dataframe(self, data_location = os.path.realpath(os.path.join(os.path.dirname(\
                                                   os.path.realpath(__file__)),\
                                                      '..', 'data', 'data.xlsx'))):
        #Used to save the updated dataframe to the data.xlsx file
        self.dataframe.to_excel(data_location, index=False)
        
        return
    
    
    ## Secondary functions:
    def load_security(self, security_name, load=False):
        
        index = self.dataframe['Name'][self.dataframe['Name'] == security_name].index[0]
        
        if load == False:
            
            sec_filepath = os.path.join(self.folder, self.dataframe['Security_loc'][index])
            index_filepath = os.path.join(self.folder, '..', 'index', self.dataframe['Index_loc'][index])
            
            sec = security(sec_filepath, index_filepath, calc_mat=False)
            
            #Create the entry in the dataframe based on the security name directly, rather than its name
            #in the Excel data sheet
            self.securities[sec.name] = sec
            
        else: 
            #Generate pickle file filename. Generated in the same way as when it is saved.
            #This only works if the names in the data.xlsx file correspond with the pickle file names
            pickle_path = os.path.join(self.folder, '..', 'pickles', \
                                  security_name.replace(' ', '_')+'.pkl')
                
            #Loading the pickle file. Note, as it had been created before the data.xlsx name should be correct
            with open(pickle_path, 'rb') as file:
                self.securities[security_name] = pickle.load(file)

        return
    
    def calc_return_matrix_per_security(self, name, **kwargs):
        self.securities[name].return_matrix = self.securities[name].calc_return_matrix(**kwargs)
        return
    
    def plot_indiv_security(self, name, **kwargs):
        self.securities[name].plot_security(**kwargs)
        return
    
