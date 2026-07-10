import fnmatch
import os
import pickle
import re

import numpy as np
import pandas as pd
import pyautogui
from investment_analyser.backtrace import Backtrace
from investment_analyser.data_loader import DataLoader
from investment_analyser.plotter import Plotter
from investment_analyser.security import Security, STANDARD_MONTH_SIZE

MARKET_FACTOR_SECURITY = "*Core*S&P*500*"


class Portfolio(Security, Plotter, DataLoader, Backtrace):
    script_location = os.path.realpath(__file__)

    def __init__(
        self,
        data_location=os.path.realpath(
            os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "data", "data.xlsx")
        ),
        months=[],
        start_date=None,
        load=False,
        overwrite_new_file_names=False,
        fetch_data=None,  # Can be "All", "non-fx", "securities", "indices" or "fx"
    ):

        Plotter.__init__(self)
        DataLoader.__init__(self)

        self.dataframe = pd.read_excel(data_location)
        valid_securities = self.dataframe["Name"].notnull()

        # Check whether all the data has been fetched:
        if fetch_data is not None:
            self.fetch_data(which=fetch_data)
        elif (
            self.dataframe["Index_loc"][valid_securities].isnull().values.any()
            or self.dataframe["Security_loc"][valid_securities].isnull().values.any()
        ):
            answer = pyautogui.confirm(
                text="Not all securities have their file locations defined.\n"
                + "Would you like to fetch all data? This may take some time.\n"
                + "If not, an attempt will be made to use the available data.",
                title="Missing Index or Security data",
                buttons=["Yes", "No"],
            )
            if answer == "Yes":
                self.fetch_data()

        # Load all the securities from the data folder into a dictionary
        self.securities = {}
        self.perform_task(
            self.dataframe["Name"][valid_securities],
            "load_securities",
            load=load,
            fx_df=self.dataframe[["Currency", "Currency_loc"]].dropna(),
        )
        security_names = list(self.securities.keys())

        if (
            overwrite_new_file_names == True and load == False and "answer" not in locals()
        ):  # Otherwise the files are reloaded i.e. had been processed before so these names should already be good
            self.dataframe["Name"][valid_securities] = security_names
            self.save_dataframe()

        # Calculate the return matrices per security:
        self.perform_task(
            security_names, "calc_return_matrix_per_security", months=months, start_date=start_date
        )

        self.months = self.securities[security_names[0]].months

        return

    def plot_portfolio(
        self, coef_type="Fitted_coef", std_mult=[1, 2, 3], limit=2, time_index=-1, coeffs=None
    ):
        # Plot the portfolio

        # Generate the input list to pass to calc_std_2D
        input_list = [self.months]

        if coeffs == None:  # Use coeffs from dataframe
            for index, element in enumerate(list(self.securities.keys())):
                input_list += [
                    self.securities[element].return_matrix,
                    self.dataframe[coef_type][index],
                ]
        else:  # manual input of coeffs for this function
            for index, element in enumerate(list(self.securities.keys())):
                input_list += [self.securities[element].return_matrix, coeffs[index]]

        # Calculate potfolio statistics
        self.std_array, self.std_err, self.return_matrix = self.calc_std_2D(*input_list)

        # Generate plot
        self.future_plot(
            self.std_array,
            self.std_err,
            self.return_matrix,
            self.months,
            std_mult,
            limit,
            time_index=time_index,
        )

        return

    def plot_securities(self, std_mult=[1, 2, 3], limit=2, time_index=-1):
        # Plot each individual security in the portfolio
        self.perform_task(
            list(self.securities.keys()),
            "plot_individual_securities",
            std_mult=std_mult,
            limit=limit,
            time_index=time_index,
        )
        return

    def fetch_data(self, which="all"):
        # Use data loader to download and clean the latest data
        # Update the data.xlsx sheet with the latest names
        #
        # Note, it is assumed there is already a downloaded version of the security files present
        # but not for the index.

        ## Set the file paths and download urls
        valid_names = self.dataframe["Name"][self.dataframe["Name"].notnull()]
        index_paths = np.empty_like(valid_names)
        index_filename = np.empty_like(index_paths)

        security_paths = np.empty_like(index_paths)
        security_filename = np.empty_like(index_paths)

        # Loop through securities to set up security path and filenames
        for index, filename in enumerate(valid_names):
            # Generating / extracting the index file name and path
            if isinstance(self.dataframe["Index_loc"][index], str):
                index_filename[index] = self.dataframe["Index_loc"][index]
            elif "Nothing" in self.dataframe["Index_down"][index]:
                index_filename[index] = "Nothing"
            else:
                index_filename[index] = filename.replace(" ", "_") + "-yahoo.csv"

            index_paths[index] = os.path.realpath(
                os.path.join(self.folder, "..", "index", index_filename[index])
            )

            # Generating / extracting the index file name and path
            if isinstance(self.dataframe["Security_loc"][index], str):
                sec_file = os.path.splitext(self.dataframe["Security_loc"][index])[0]
            else:
                sec_file = re.search(
                    "fileName.+(?=&)", self.dataframe["Security_down"][index]
                ).group(0)[9:]

            security_filename[index] = (
                sec_file
                + "."
                + re.search("fileType.+(?=&f)", self.dataframe["Security_down"][index]).group(0)[9:]
            )

            security_paths[index] = os.path.join(self.folder, security_filename[index])

            # Changing the ext. to save the security files correctly after having been cleaned
            security_filename[index] = (
                security_filename[index][: security_filename[index].rfind(".")] + ".xlsx"
            )

        if which == "indices" or which == "non-fx" or which == "all":
            # Download the index files
            self.download_indices(self.dataframe["Index_down"], index_paths)

            # Add the new index filenames to the dataframe and save
            self.dataframe["Index_loc"] = index_filename

        if which == "securities" or which == "non-fx" or which == "all":
            # Download the security files (no specific securities wrapper is needed for iShares, they are
            # automatically up-to-date)
            self.perform_download(self.dataframe["Security_down"], security_paths, "Securities")

            # Clean the iShares files
            self.clean_files()

            # Add the new security filenames to the dataframe and save
            self.dataframe["Security_loc"] = security_filename

        if which == "fx" or which == "all":
            print("FX files should be downloaded manually for now.")
            # fx_paths = np.empty_like(self.dataframe["Currency"])
            # fx_filename = np.empty_like(fx_paths)

            # for index, filename in enumerate(self.dataframe["Currency"]):
            #     # Generating / extracting the index file name and path
            #     if isinstance(self.dataframe["Currency_loc"][index], str):
            #         fx_filename[index] = self.dataframe["Currency_loc"][index]
            #     else:
            #         fx_filename[index] = filename.replace(" ", "_") + "-fxtop.csv"

            #     fx_paths[index] = os.path.realpath(
            #         os.path.join(self.folder, "..", "fx", fx_filename[index])
            #     )

            # # Download the security files (no specific securities wrapper is needed for iShares, they are
            # # automatically up-to-date)
            # self.perform_download(self.dataframe["Currency_down"], fx_paths, "FX")

            # # Add the new security filenames to the dataframe and save
            # self.dataframe["Currency_loc"] = fx_filename

        self.save_dataframe()

        return

    def optimise(self, months=None, start_date=None):
        # Find the most optimised portfolio, given input on priorities
        securities = self.securities.copy()

        tick_intervals, market_std_factor, market_std_err_factor = self._calculate_market_factor(
            MARKET_FACTOR_SECURITY
        )

        no_sec = len(securities.keys())
        no_months = len(months)

        return_vector = np.empty((no_months,no_sec))
        cov_matrix = np.empty_like((no_months, no_sec, no_sec))
        upside_cov_matrix = np.empty_like(cov_matrix)
        downside_cov_matrix = np.empty_like(cov_matrix)
        # start_tick_matrix = np.empty_like(cov_matrix) # Used later for market factors

        # Calculate factors per security (no cross-terms yet)
        for index, (key, security) in enumerate(securities.items()):
            if start_date is not None:
                _, tick_time, return_series = security._set_start_tick(start_date)
            else:
                start_tick = self.tick_time[0]
                tick_time = self.tick_time.copy()
                return_series = self.return_series.copy()

            return_mx = self.calc_return_matrix(
                months=months, tick_time=tick_time, return_series=return_series
            )

            # Find the relevant market-correction factor
            market_factor_index = np.argmin(np.abs(tick_intervals - start_tick))

            (
                return_value,
                cov_value,
                downside_cov_value,
                upside_cov_value,
                _,
                _,
            ) = self.calc_cov(return_mx)

            return_vector[:, index] = return_value / market_std_factor[:,0,market_factor_index]
            cov_matrix[:, index, index] = cov_value / market_std_factor[:,1,market_factor_index]
            downside_cov_matrix[:, index, index] = downside_cov_value / market_std_factor[:,2,market_factor_index]
            upside_cov_matrix[:, index, index] = upside_cov_value / market_std_factor[:,3,market_factor_index]

        for index, (key, security) in enumerate(securities.items()):
            if start_date is not None:
                start_tick, tick_time, return_series = security._set_start_tick(start_date)
            else:
                start_tick = self.tick_time[0]
                tick_time = self.tick_time.copy()
                return_series = self.return_series.copy()

            remaining_securities = dict(securities)
            del remaining_securities[key]

            for sub_index, (sub_key, sub_security) in enumerate(remaining_securities.items()):
                sub_start_tick = np.max(start_tick, sub_security.tick_time[0])
                sub_end_tick = np.min(tick_time[-1], sub_security.tick_time[-1])

                # Slice main security
                start_index = np.argmin(abs(tick_time - sub_start_tick))
                end_index = np.argmin(abs(tick_time - sub_end_tick))
                sub_tick_time = tick_time[start_index:end_index]
                sub_return_series = return_series[start_index:end_index]

                # Slice other security
                start_index = np.argmin(abs(sub_security.tick_time - sub_start_tick))
                end_index = np.argmin(abs(sub_security.tick_time - sub_end_tick))
                other_sec_tick_time = sub_security.tick_time[start_index:end_index]
                other_sec_return_series = sub_security.return_series[start_index:end_index]

                if len(sub_tick_time) != len(other_sec_tick_time):
                    raise ValueError(
                        f"Tick time lengths are not equal for '{key}' and '{sub_key}': "
                        f"{len(sub_tick_time)} != {len(other_sec_tick_time)}"
                    )

                sub_return_mx = self.calc_return_matrix(
                    months=months, tick_time=sub_tick_time, return_series=sub_return_series
                )
                other_return_mx = self.calc_return_matrix(
                    months=months,
                    tick_time=other_sec_tick_time,
                    return_series=other_sec_return_series,
                )

                _, cov, hedging_cov, gains_cov, _, _ = self.calc_cov(
                    sub_return_mx, other_return_mx
                )


        return

    def save_dataframe(
        self,
        data_location=os.path.realpath(
            os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "data", "data.xlsx")
        ),
    ):
        # Used to save the updated dataframe to the data.xlsx file
        self.dataframe.to_excel(data_location, index=False)

        return

    ## Secondary functions:
    def _calculate_market_factor(self, market_security_wildcard, months):
        """Returns market scaling factors for return parameters based on data intervals"""
        matches = [
            key
            for key in self.securities.keys()
            if fnmatch.fnmatchcase(key, market_security_wildcard)
        ]

        if len(matches) == 0:
            raise KeyError(f"No security matched wildcard '{market_security_wildcard}'.")
        if len(matches) > 1:
            raise ValueError(
                f"Multiple securities matched wildcard '{market_security_wildcard}': {matches}"
            )

        sec = self.securities[matches[0]]

        tick_intervals = np.arange(
            sec.tick_time[0], sec.tick_time[-1] - np.max(months) * STANDARD_MONTH_SIZE, 180
        )
        # Assign empty array (note, 8 is for the 8 different elements in the calc_std_1D output)
        market_std_factor = np.empty((len(months), 8, len(tick_intervals)))
        market_std_err_factor = np.empty_like(market_std_factor)
        start_indices = np.asarray(tick_intervals - tick_intervals[0], dtype=int)

        for ind, start_index in enumerate(start_indices):
            tick_time = sec.tick_time[start_index:]
            return_series = sec.return_series[start_index:]

            return_matrix = sec.calc_return_matrix(
                months=months, tick_time=tick_time, return_series=return_series
            )

            # Calculate statistics
            market_std_factor[:, :, ind], market_std_err_factor[:, :, ind] = sec.calc_std_1D(
                return_matrix, months
            )

        # Normalise to the full length market data (at ind = 0).
        # This factor now provides a factor
        market_std_factor /= market_std_factor[:, :, 0:1]
        market_std_err_factor /= market_std_err_factor[:, :, 0:1]

        return tick_intervals, market_std_factor, market_std_err_factor

    def load_securities(self, security_name, load=False, fx_df=None):

        index = self.dataframe["Name"][self.dataframe["Name"] == security_name].index[0]
        if self.dataframe["Used"][index] == 0:
            print(f"\n{security_name} is not used in the portfolio, skipping...")
            return

        if (
            not isinstance(self.dataframe["Security_loc"][index], str)
            or self.dataframe["Security_loc"][index] == ""
        ):
            print(f"\nNo security location defined for {security_name}, skipping...")
        else:
            if load == False:
                sec_filepath = os.path.join(self.folder, self.dataframe["Security_loc"][index])
                dist_fund = self.dataframe["Dist_fund"][index] == 1

                if isinstance(self.dataframe["Index_loc"][index], str):
                    index_filepath = os.path.join(
                        self.folder, "..", "index", self.dataframe["Index_loc"][index]
                    )
                    sec = Security(
                        sec_filepath,
                        index_filepath,
                        dist_fund=dist_fund,
                        fx_df=fx_df,
                        calc_mat=False,
                        name=security_name,
                    )
                else:
                    sec = Security(
                        sec_filepath,
                        dist_fund=dist_fund,
                        fx_df=fx_df,
                        calc_mat=False,
                        name=security_name,
                    )

                # Create the entry in the dataframe based on the security name directly, rather than its name
                # in the Excel data sheet
                self.securities[sec.name] = sec

            else:
                # Generate pickle file filename. Generated in the same way as when it is saved.
                # This only works if the names in the data.xlsx file correspond with the pickle file names
                pickle_path = os.path.join(
                    self.folder, "..", "pickles", security_name.replace(" ", "_") + ".pkl"
                )

                # Loading the pickle file. Note, as it had been created before the data.xlsx name should be correct
                with open(pickle_path, "rb") as file:
                    self.securities[security_name] = pickle.load(file)

        return

    def calc_return_matrix_per_security(self, name, **kwargs):
        self.securities[name].return_matrix = self.securities[name].calc_return_matrix(**kwargs)
        return

    def plot_individual_securities(self, name, **kwargs):
        self.securities[name].plot_security(**kwargs)
        return
