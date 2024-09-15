import numpy as np
import os
import pandas as pd
import pickle
import pyautogui
import re
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
        
        #Check whether all the data has been fetched:
        if self.dataframe['Index_loc'].isnull().values.any() or \
            self.dataframe['Security_loc'].isnull().values.any():
            answer = pyautogui.confirm(text='Not all securities have their file locations defined.\n'\
                              +'Would you like to fetch all data? This may take some time.\n'+
                              'If not, an attempt will be made to use the available data.',\
                                  title='Missing Index or Security data',\
                                      buttons=['Yes', 'No'])
            if answer == 'Yes':
                self.fetch_data()
        
        
        #Load all the securities from the data folder into a dictionary
        self.securities = {}        
        self.perform_task(self.dataframe['Name'], 'load_securities', load)
        
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
        self.perform_task(list(self.securities.keys()), 'plot_individual_securities', \
                          std_mult=std_mult, limit=limit, time_index=time_index)            
        return
        
    def fetch_data(self, which='all'):
        #Use data loader to download and clean the latest data
        #Update the data.xlsx sheet with the latest names
        #
        #Note, it is assumed there is already a downloaded version of the security files present
        # but not for the index.
        
        
        ## Set the file paths and download urls
        index_paths = np.empty_like(self.dataframe['Name'])
        index_filename = np.empty_like(index_paths)
        
        security_paths = np.empty_like(index_paths)
        security_filename = np.empty_like(index_paths)
        
        #Loop through securities to set up security path and filenames
        for index, filename in enumerate(self.dataframe['Name']):
            #Generating / extracting the index file name and path
            if isinstance(self.dataframe['Index_loc'][index], str):
                index_filename[index] = self.dataframe['Index_loc'][index]
            else:
                index_filename[index]= filename.replace(' ', '_') + '-yahoo.csv'
                
            index_paths[index] = os.path.realpath(os.path.join(self.folder, '..', 'index', index_filename[index]))
            
            #Generating / extracting the index file name and path
            if isinstance(self.dataframe['Security_loc'][index], str):
                sec_file = os.path.splitext(self.dataframe['Security_loc'][index])[0]
            else:
                sec_file = re.search('fileName.+(?=&)', self.dataframe['Security_down'][index]).group(0)[9:]
            
            security_filename[index] = sec_file + '.' +\
                re.search('fileType.+(?=&f)', self.dataframe['Security_down'][index]).group(0)[9:]
           

            security_paths[index] = os.path.join(self.folder, security_filename[index])
            
            #Changing the ext. to save the security files correctly after having been cleaned
            security_filename[index] = security_filename[index][:security_filename[index].rfind('.')] + '.xlsx'

        
        if which == 'indices' or which == 'non-fx' or which == 'all':
            #Download the index files     
            self.download_indices(self.dataframe['Index_down'], index_paths)
            
            #Add the new index filenames to the dataframe and save
            self.dataframe['Index_loc'] = index_filename
        
        if which == 'securities' or which == 'non-fx' or which == 'all':
            #Download the security files (no specific securities wrapper is needed for iShares, they are
            #automatically up-to-date)
            self.perform_download(self.dataframe['Security_down'], security_paths, 'Securities')
            
            #Clean the iShares files
            self.clean_files()
            
            #Add the new security filenames to the dataframe and save
            self.dataframe['Security_loc'] = security_filename
            
        if which == 'fx' or which == 'all':
            
            fx_paths = np.empty_like(self.dataframe['Currency'])
            fx_filename = np.empty_like(fx_paths)
            
            for index, filename in enumerate(self.dataframe['Currency']):
                #Generating / extracting the index file name and path
                if isinstance(self.dataframe['Currency_loc'][index], str):
                    fx_filename[index] = self.dataframe['Currency_loc'][index]
                else:
                    fx_filename[index]= filename.replace(' ', '_') + '-fxtop.csv'
                    
                fx_paths[index] = os.path.realpath(os.path.join(self.folder, '..', 'fx', fx_filename[index]))
                
            
            
            #Download the security files (no specific securities wrapper is needed for iShares, they are
            #automatically up-to-date)
            self.perform_download(self.dataframe['Currency_down'], fx_paths, 'FX')
            
            #Add the new security filenames to the dataframe and save
            self.dataframe['Currency_loc'] = fx_filename
            
        self.save_dataframe()
        
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
    def load_securities(self, security_name, load=False):
        
        index = self.dataframe['Name'][self.dataframe['Name'] == security_name].index[0]
        
        if load == False:
            sec_filepath = os.path.join(self.folder, self.dataframe['Security_loc'][index])
            
            if isinstance(self.dataframe['Index_loc'][index], str):
                index_filepath = os.path.join(self.folder, '..', 'index', self.dataframe['Index_loc'][index])
                sec = security(sec_filepath, index_filepath, calc_mat=False)
            else:
                sec = security(sec_filepath, calc_mat=False)
                
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
    
    def plot_individual_securities(self, name, **kwargs):
        self.securities[name].plot_security(**kwargs)
        return
    
