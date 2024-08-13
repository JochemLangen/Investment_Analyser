# -*- coding: utf-8 -*-


import pandas as pd
from bs4 import BeautifulSoup
import os
import sys
from IA_base import *

class data_loader(base):
    script_location = os.path.realpath(__file__)
    
    def __init__(self, folder_location = os.path.realpath(
            os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                                      '..', 'data'))):
        self.folder = folder_location # default = <repo. location>\data
        return
    
    
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


    def download_data(self):
        print("Placeholder function! \nA list can be provided with the download locations " +
              "of all data files, these can then be moved to the right location and cleaned up.")
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
                    
                    #Read as html instead
                    soup = BeautifulSoup(file_contents)
                    
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
        
    
    # def __process_bar(self, inc, fpath):
    #     sys.stdout.write('\r')
    #     sys.stdout.write("[%-50s] %5.2f%% Current file: %s" % ('='*int(inc//2), inc, fpath))
    #     sys.stdout.flush()
    #     return

