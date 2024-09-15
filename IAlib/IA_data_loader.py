# -*- coding: utf-8 -*-


import pandas as pd
from bs4 import BeautifulSoup
import os
import sys
import re
import datetime
import concurrent.futures
import requests
import json
from http.client import responses
from selenium import webdriver 
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from IA_base import *

class data_loader(base):
    script_location = os.path.realpath(__file__)
    
    def __init__(self, folder_location = os.path.realpath(
            os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                                      '..', 'data', 'security'))):
        self.folder = folder_location # default = <repo. location>\data
        self.download_status = 0
        self.download_folder = "D:\Jochem\Downloads"
        return
    
    ## Cleaning files:
        
    def clean_files(self):
        print("Cleaning up data files in: \n" + self.folder + "\n")
        
        # List of all files to be cleaned, currently this assumes all to be cleaned files
        # are in XML format and should become .xlsx
        cleaning_files = []
        
        # Walking through all data folders:
        for (root, dirs, files) in os.walk(self.folder):
            for file in files: # Loop through all files in the current folder

                # Extract the file extension
                file_ext = os.path.splitext(file)[1]
                
                # Check the file type (data source -> determines how it should be handled)
                if file.find('iShares') != -1 and (file_ext == '.xls' or file_ext == '.xlsx'): 
                    # For iShares, .xls files are not formatted correctly yet
                    if file_ext == '.xls': 
                        # Add files to the "to be cleaned list
                        fpath = os.path.realpath(os.path.join(root, file))
                        cleaning_files += [fpath]
                else:
                    fpath = os.path.join(root, file)
                    raise ValueError("The following data file has been found but is not supported: \n" + 
                                     fpath + "\n" + "If this file type should be supported, implement it in: \n" +
                                     self.script_location + "\n\nCurrently, the only supported files are: \n" + 
                                     "'iShares*.xls'\n'iShares*.xlsx'")
        
        self.perform_task(cleaning_files, "xml_to_xlsx")
    
        return
    
    def xml_to_xlsx(self, fpath):
        
        newpath = os.path.realpath(fpath[:fpath.rfind('.')] + '.xlsx')
        
        try:
            with open(fpath) as xml_file:
                # Scrape all data out of xml file using BeautifulSoup library
                file_contents = xml_file.read()
                soup = BeautifulSoup(file_contents, 'xml')
                
                # Check if the file can be read out properly as xml file
                if len(soup.findAll('Worksheet')) == 0:
                    
                    #Read with lxml instead
                    soup = BeautifulSoup(file_contents, 'lxml')
                    
                    # Find out the formatting used to determine sheets, rows and cells
                    flag_format_sheet = ['Worksheet', 'ss:worksheet', 'worksheet', 'ss:Worksheet']
                    flag_format_row = ['Row', 'ss:row', 'row', 'ss:Row']
                    flag_format_cell = ['Cell', 'ss:cell', 'cell', 'ss:Cell']
                    flag_format_name = ['ss:Name', 'ss:name', 'ss:name', 'ss:Name']
                    flag_format_data = ['ss:Data', 'ss:data', 'ss:data', 'ss:Data']
                    
                    for i, sheetflag in enumerate(flag_format_sheet):
                        if len(soup.findAll(sheetflag)) == 0 and i < 3:
                            continue
                        elif i == 3:
                            raise ValueError('The XML/HTML format could not be determined! \n')
                        else:
                            rowflag = flag_format_row[i]
                            cellflag = flag_format_cell[i]
                            nameflag = flag_format_name[i]
                            dataflag = flag_format_data[i]
                            break
                        
                    # Create the new file to fill
                    writer = pd.ExcelWriter(newpath)
                    
                    # Loop through all sheets to re-create them in the new file
                    for sheet in soup.findAll(sheetflag):
                        # Create variable to put the contents of the sheet in and loop through the data structure rows
                        sheet_as_list = []
                        for row in sheet.findAll(rowflag):
                            # Within each row of the data structure, find all cell elements in the xml structure.
                            # Those cells contain the data value and the style information.
                            # For all cells with non-empty data, append the data to the sheet list as a new row.
                            row_as_list = []
                            for cell in row.findAll(cellflag):
                                data = cell.findAll(dataflag)[0] #Extract the data string
                                row_as_list += [data.text if data.text else '']
                            
                            sheet_as_list.append(row_as_list)

                        # Convert the list into a sheet and add it to the Excel file
                        pd.DataFrame(sheet_as_list).to_excel(writer, sheet_name=sheet.attrs[nameflag], index=False, header=False)

                else: # Use as XML file
                    # Create the new file to fill
                    writer = pd.ExcelWriter(newpath)
                    
                    # Loop through all sheets to re-create them in the new file
                    for sheet in soup.findAll('Worksheet'):
                        # Create variable to put the contents of the sheet in and loop through the data structure rows
                        sheet_as_list = []
                        for row in sheet.findAll('Row'):
                            # Within each row of the data structure, find all cell elements in the xml structure.
                            # Those cells contain the data value and the style information.
                            # For all cells with non-empty data, append the data to the sheet list as a new row.
                            sheet_as_list.append([cell.Data.text if cell.Data else '' for cell in row.findAll('Cell')])

                        # Convert the list into a sheet and add it to the Excel file
                        pd.DataFrame(sheet_as_list).to_excel(writer, sheet_name=sheet.attrs['ss:Name'], index=False, header=False)
   
                # Close the Excel file (i.e. save)
                writer.close()
        except (ValueError, IndexError):
            xml_file.close()
            print("\n\nSomething went wrong reading the original file. \n"
                  + "This can have been caused by a bad path (i.e. nothing is read). \n"+
                  "Check if this gives a valid output: os.path.realpath(<your path variable>).\n" +
                  "Or the file might have been open already (i.e. can't be accessed). Close it!" + 
                  "\nIf none of this worked, check the xml styling, compatibility might need to be added in: \n" +
                  self.script_location)
            raise
        
        # Delete the old file
        os.remove(fpath)
        return




    ## Downloading files:
        
    def download_indices(self, url_templates, filenames):
        #Loop through a list of url templates from the dataframe, these are used to generate
        #All the urls which are threaded, downloaded and then recombined.
        #It currently only supports Yahoo Finance data
        url_templates = np.array(url_templates)
        
        current_time = datetime.datetime.now()
        timestamp = str(int(np.floor(current_time.timestamp())))
        urls = np.empty_like(url_templates)
        
        for index, url_temp in enumerate(url_templates):
            if "finance.yahoo" in url_temp:
                #Change date to current month
                #Yahoo dates start counting from 02/01/1970 with tickers being year + day + hour + min + sec
                urls[index] = re.sub('period2=.+(?=&interval)', 'period2='+timestamp, url_temp)
                
                #Limit data to 01-01-19700
                if int(re.search('period1=.+(?=&period2)', urls[index]).group(0)[8:]) < 7200:
                    urls[index] = re.sub('period1=-.+(?=&period2)', 'period1=7200', urls[index]) #Set lowest start time to 1971-01-02 (i.e. 0 ticker)

            else:
                raise ValueError('Currently, only Yahoo Finance index data sets are supported.')
            
        self.perform_download(urls, filenames, 'Index files')
        
        return
    
    def download_fx(self, url_templates, filenames):
        #Loop through a list of url templates from the dataframe, these are used to generate
        #All the urls which are threaded, downloaded and then recombined.
        #It currently only supports fxtop and ECB
        url_templates = np.array(url_templates)
        
        current_time = datetime.datetime.now()
        month = str(current_time.month).zfill(2) #Get the month and add zero if needed
        year = str(current.time.year)
        urls = np.empty_like(url_templates)
        
        #Don't redownload ecb data
        url_templates = url_templates[['ecb.europa.eu' not in x for x in url_templates]]

        for index, url_temp in enumerate(url_templates):
            if "fxtop" in url_temp:
                #Change date to current month
                urls[index] = re.sub('MM2=.+(?=&Y)', 'MM2='+month, url_temp)
                urls[index] = re.sub('YYYY2=-.+(?=&b)', 'YYYY2='+year, urls[index])

            else:
                raise ValueError('Currently, only FXTOP fx data sets are supported.')
            
        self.perform_download(urls, filenames, 'FX files')
        
        return
        
    
    
    def perform_download(self, urls, filenames, title):
        print('\nDownloading: ' + title)
        nelem = len(urls)
        
        if nelem != 0:
            # Determine the step increment for the process bar:
            self.processing_inc = round(100/nelem, 2)
            
            # Create every download as a thread and pool all to be downloaded simultaneously
            # with ThreadPoolExecutor() as executor:
            #     executor.map(data_loader.download_file, urls, filenames)
            with concurrent.futures.ThreadPoolExecutor() as executor:
                result_futures  = list(map(lambda x, y: executor.submit(self.download_file, x, y), \
                                   urls, filenames))
                    
                #Check if there's an error and throw
                for future in concurrent.futures.as_completed(result_futures):
                    if future.result() != None:
                        raise ConnectionError(future.result())
        else:
            item = 'Nothing to download'

        # Done!    
        self.process_bar(100, item)
        print('\n')
        
        # Reset download status and remove processing_inc
        delattr(self, 'processing_inc')
        self.download_status = 0
        return
    
    
    def download_file(self, url, filename):
        
        if 'msci.com' in url:
            self.driver_download(url, filename)
        else:
        
            response = requests.get(url, headers = {'User-agent': 'InkJDog'})
            
            # Check the error code
            try:
                response.raise_for_status()
            except:
                  return 'Request failed with error: ' + str(response.status_code) + ' - '\
                     + responses[response.status_code] +'\n'\
                           'For file: ' + filename + '\nWith url: ' + url
            
            if 'finance.yahoo' in url: #Yahoo json file
                self.extract_yahoo_json(response.content, filename)
            
            elif 'fxtop' in url: #FXTOP fx file
                self.extract_fxtop_html(response.content, filename)    
            
            else:
                with open(filename, mode="wb") as file:
                    file.write(response.content)
            
        self.download_status += 1
        self.process_bar(self.download_status*self.processing_inc, filename)            
            
        return
    
    def extract_yahoo_json(self, content, filename):
        #Load yahoo html chart data as json file, extract data and save as csv
        
        js = json.loads(content)
        
        df = pd.DataFrame(data = {'Timestamp': js['chart']['result'][0]['timestamp'],\
                                  'Adj Close': js['chart']['result'][0]['indicators']['adjclose'][0]['adjclose']}\
                          , dtype=float)
        
        df.to_csv(filename, index=False)
        return
    
    def extract_fxtop_html(self, content, filename):
        #Load html table from html page source code and save as csv
        
        #Read the html page content into pandas dataframe. The output is an
        #array of dataframes
        df_list = pd.read_html(content)
        
        #Extract the largest dataframe from the list (this will be the table)
        df = df_list[np.argmax([x.size for x in df_list])]
        
        df.to_csv(filename, index=False)
        return
    
    def driver_download(self, url, filename):
        #Open webpage to download the file
        
        driver = webdriver.Chrome()
        #Set the waiting time for trying to find elements that have not been found
        driver.implicitly_wait(10) 
        
        driver.get(url)
        
        #Change the term:
        element = WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((webdriver.common.by.By.XPATH,\
                                        "//select[contains(@id, 'updateTerm')]")))
        select = Select(element)
        
        # select by visible text
        select.select_by_visible_text('Full History')
        
        #Update data
        element = WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((webdriver.common.by.By.XPATH,\
                                        "//button[text()='Update']")))
        element.click()
        
            
        #Find the download button
        element = WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((webdriver.common.by.By.XPATH,\
                                        "//a[contains(text(), 'Download')]")))
        
        #Click!
        download_timestamp = datetime.datetime.now().timestamp()
        element.click()
        
        #Check if the file has downloaded:
        still_downloading = True
        while still_downloading:
            time.sleep(.6)
            newest_file = latest_download_file(self.download_folder, True)
            if newest_file > download_timestamp:
                still_downloading = False
        
        #Close once it has been downloaded
        driver.close()
        
        new_df = pd.read_excel(self.latest_download_file(self.download_folder, False))
        df = pd.read_excel(filename)
        
        #Find last data index
        nan_inds = df.isnull(df).any(0).nonzero()[0]
        df_last_index = nan_inds[nan_inds > 20][0] #Skip the set of nans at the top -> first one at the bottom
        
        nan_inds = new_df.isnull(df).any(0).nonzero()[0]
        new_df_last_index = nan_inds[nan_inds > 20][0] #Skip the set of nans at the top -> first one at the bottom
        
        #Find the index to match:
        
        
        
    def latest_download_file(self, download_dir, return_time):
        os.chdir(download_dir)
        files = sorted(os.listdir(os.getcwd()), key=os.path.getmtime)
        if return_time:
            return os.path.getmtime(files[-1])
        else:
            return os.path.join(download_dir, files[-1])
