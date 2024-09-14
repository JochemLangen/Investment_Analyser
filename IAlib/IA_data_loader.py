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
from IA_base import *

class data_loader(base):
    script_location = os.path.realpath(__file__)
    
    def __init__(self, folder_location = os.path.realpath(
            os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                                      '..', 'data', 'security'))):
        self.folder = folder_location # default = <repo. location>\data
        self.download_status = 0
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
                #Yahoo dates start counting from 02/01/1970 with tickers being year + day + hour + min + sec
                urls[index] = re.sub('period2=.+(?=&interval)', 'period2='+timestamp, url_temp)
                urls[index] = re.sub('period1=-.+(?=&period2)', 'period1=7200', urls[index]) #Set lowest start time to 1971-01-02 (i.e. 0 ticker)

            else:
                raise ValueError('Currently, only Yahoo Finance index data sets are supported.')
            
        self.perform_download(urls, filenames, 'Index files')
        
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
        response = requests.get(url, headers = {'User-agent': 'InkJDog'})
        
        # Check the error code
        try:
            response.raise_for_status()
        except:
              return 'Request failed with error: ' + str(response.status_code) + ' - '\
                 + responses[response.status_code] +'\n'\
                       'For file: ' + filename + '\nWith url: ' + url
        
        if 'finance.yahoo' in url: #Yahoo json file
            self.json_to_csv(response.content, filename)
        
        else:
            with open(filename, mode="wb") as file:
                file.write(response.content)
            
        self.download_status += 1
        self.process_bar(self.download_status*self.processing_inc, filename)            
            
        return
    
    def json_to_csv(self, content, filename):
        #Load yahoo html chart data as json file, extract data and save as csv
        
        js = json.loads(content)
        
        df = pd.DataFrame(data = {'Timestamp': js['chart']['result'][0]['timestamp'],\
                                  'Adj Close': js['chart']['result'][0]['indicators']['adjclose'][0]['adjclose']}\
                          , dtype=float)
        
        df.to_csv(filename, index=False)
        return
