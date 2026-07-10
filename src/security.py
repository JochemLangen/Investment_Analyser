import datetime
import os
import pickle

import numpy as np
import pandas as pd
from investment_analyser.backtrace import Backtrace
from investment_analyser.plotter import Plotter
from investment_analyser.data_loader import DataLoader
from scipy.interpolate import PchipInterpolator

BASE_CURRENCY = "GBP"
class Security(Plotter, DataLoader, Backtrace):
    script_location = os.path.realpath(__file__)

    # Zero point after which to start counting (at 1953 01 Jan, tick = 1)
    # This must be a leap year
    zero_point = 1952

    def __init__(
        self, fpath, index_fpath=None, dist_fund=False, months=[],
        fx_df=None, backtrace=True, calc_ortho=True,
        start_date=None, calc_mat=True, name=None,
    ):
        #
        # start_date: format is dd/mm/yyyy. Minimum is 02/01/1970
        Plotter.__init__(self)
        DataLoader.__init__(self)

        self.__extract_security(fpath, dist_fund=dist_fund, name=name)

        if index_fpath is not None and "Nothing" not in index_fpath:
            self.__extract_index(index_fpath)
            index_available = True
        else:
            index_available = False
            self.index_return_series = []
            self.index_tick_time = []
            self.orig_index_tick_time = []

        if fx_df is not None:
            self.__apply_fx(fx_df)

        if backtrace and index_available:
            self.return_series, self.tick_time, self.orig_tick_time, self.backtracing = self.backtrace_data(
                y=self.return_series,
                y_old=self.index_return_series,
                t=self.tick_time,
                t_old=self.index_tick_time,
                t_orig=self.orig_tick_time,
                t_orig_old=self.orig_index_tick_time,
                calc_ortho=calc_ortho,
                benchmark=self.benchmark
            )
        else:
            self.backtracing = []

        self.start_tick, self.tick_time, self.return_series = self._set_start_tick(start_date)
        self.months, _ = self.generate_intervals(months=months)

        self.save_security()

        if calc_mat == True:
            self.return_matrix = self.calc_return_matrix(self.months, start_date)

        return

    def __extract_security(self, fpath, dist_fund=False, name=None):

        ## Extract the data
        # Extract the file extension
        file_ext = os.path.splitext(fpath)[1]

        # Check the file type (data source -> determines how it should be handled)
        if (fpath.find("iShares") != -1 or fpath.find("STOXX") != -1) and file_ext == ".xlsx":

            file_name = os.path.basename(fpath).split('/')[-1]

            # Read the excel file:
            if "ETC" in file_name and "ETF" not in file_name:
                # It is an ETC (physical commodity) rather than equity/bond ETF
                excel = pd.read_excel(fpath, sheet_name=[0, 1], header=None)

                sheet1 = excel[0]
                sheet2 = excel[1]
            else:
                if dist_fund == True:
                    excel = pd.read_excel(fpath, sheet_name=[1, 2, 4], header=None)
                else:
                    excel = pd.read_excel(fpath, sheet_name=[1, 2], header=None)

                sheet1 = excel[1]
                sheet2 = excel[2]

            # Name of the security (first row, first column)
            if name is None:
                self.name = sheet1.iloc[0, 0]
            else:
                self.name = name

            # Helper to find the first row in column 0 that contains a given label (case-insensitive)
            def _find_row(label: str | list[str]):
                col0 = sheet1.iloc[:, 0].astype(str)
                labels = [label] if isinstance(label, str) else label

                for candidate in labels:
                    mask = col0.str.contains(candidate, case=False, na=False)
                    if mask.any():
                        return int(np.where(mask.values)[0][0])

                raise ValueError(
                    f"Could not find row containing any of {labels} in column 0 of: {fpath}"
                )

            # Find inception date (first entry whose column-0 contains "Date")
            row_date = _find_row("Date")
            self.inception = sheet1.iloc[row_date, 1]
            self.inception_tick = self.convert_time(np.asarray([self.inception]), time_form="iShares")[0]

            # Find type (row where column-0 contains "Class")
            row_type = _find_row("Class")
            self.type = sheet1.iloc[row_type, 1]

            # Find benchmark (row where column-0 contains "Benchmark")
            row_benchmark = _find_row(["Benchmark", "Index"])
            self.benchmark = sheet1.iloc[row_benchmark, 1]

            # Find currency (row where column-0 contains "Base Currency")
            row_currency = _find_row("Base Currency")
            self.currency = sheet1.iloc[row_currency, 1]

            orig_ticks = self.convert_time(np.asarray(sheet2[0][1:]), time_form="iShares")
            orig_return = sheet2[5][1:]

            # Remove entries with '--' and reverse order (from start to now)
            numeric_entries = ~orig_return.str.contains("-", na=False)
            self.orig_tick_time = orig_ticks[numeric_entries][::-1]
            orig_return = np.asarray(orig_return[numeric_entries][::-1], dtype=float)

            ## Interpolate data to full dataset
            # (interpolation is done so the return can be calculated on all data and sampling
            # biases are removed)
            self.tick_time = np.arange(self.orig_tick_time[0], self.orig_tick_time[-1]+1, 1, dtype=int)
            # Perform interpolation (pchip is used for most accurate interpolation, without overshooting)
            self.return_series = PchipInterpolator(self.orig_tick_time, orig_return)(self.tick_time)

            if dist_fund:
                dividend_sheet = excel[4]
                dividend_headers = dividend_sheet.iloc[0].astype(str)

                payable_col = np.where(dividend_headers.str.contains("Payable", case=False, na=False))[0]
                total_col = np.where(dividend_headers.str.contains("Total", case=False, na=False))[0]

                if len(payable_col) == 0:
                    raise ValueError("Could not find a dividend 'Payable' column in the dividend sheet.")
                if len(total_col) == 0:
                    raise ValueError("Could not find a dividend 'Total' column in the dividend sheet.")

                dividend_tick_time = self.convert_time(
                    np.asarray(dividend_sheet.iloc[1:, int(payable_col[0])]), time_form="iShares"
                )
                dividend_return = dividend_sheet.iloc[1:, int(total_col[0])]

                # Remove entries with '--' and reverse order (from start to now)
                numeric_entries_div = ~dividend_return.str.contains("-", na=False)
                dividend_tick_time = dividend_tick_time[numeric_entries_div][::-1]
                valid_dividends = dividend_tick_time <= self.tick_time[-1]
                dividend_tick_time = dividend_tick_time[valid_dividends]

                dividend_return = np.asarray(dividend_return[numeric_entries_div][::-1][valid_dividends], dtype=float)

                # Extract per security NAV in security currency
                nav = sheet2[2][1:]

                numeric_entries_nav = ~nav.str.contains("-", na=False)
                nav = nav[numeric_entries_nav][::-1]
                orig_nav_ticks = orig_ticks[numeric_entries_nav][::-1]

                nav = PchipInterpolator(orig_nav_ticks, nav)(self.tick_time)

                # Align NAV values to the dividend dates in a vectorized way.
                idx = np.searchsorted(self.tick_time, dividend_tick_time)

                # Check if the dividends do actually fall within the nav time-series (in principle
                # it always should)
                if idx[-1] >= len(self.tick_time):
                    idx = idx[:-1]
                    dividend_return = dividend_return[:-1]

                if (
                    (not len(self.tick_time[idx]) == len(dividend_tick_time)) or
                    (not np.all(self.tick_time[idx] == dividend_tick_time))
                ):
                    raise ValueError("Some dividend dates could not be matched to NAV dates.")

                dividend_nav = np.asarray(nav[idx], dtype=float)
                rel_dividend_return = 1 + dividend_return / dividend_nav

                # Apply dividend effects to all subsequent returns in a vectorized way.
                dividend_factors = np.ones(len(self.return_series), dtype=float)
                dividend_factors[idx] = rel_dividend_return
                dividend_factors = np.cumprod(dividend_factors)
                self.return_series *= dividend_factors

        elif (fpath.find("iShares") != -1 or fpath.find("STOXX") != -1) and file_ext == ".xls":
            raise ValueError(
                "The .xls file should be converted to a .xlsx file first. \n"
                + "Use the data loader to do this."
            )
        else:
            raise ValueError(
                "The following data file has been found but is not supported: \n"
                + fpath
                + "\n"
                + "If this file type should be supported, implement it in: \n"
                + self.script_location
                + "\n\nCurrently, the only supported files are: \n"
                + "'iShares*.xls'\n'iShares*.xlsx'"
            )

        return

    def __extract_index(self, fpath):

        ## Extract the data
        # Extract the file extension
        file_ext = os.path.splitext(fpath)[1]

        # Check the file type (data source -> determines how it should be handled)
        if fpath.find("yahoo") != -1 and file_ext == ".csv":
            # Read csv file
            excel = pd.read_csv(fpath)

            if "Date" in excel.columns:  # Old format, with download API:
                # Extract time
                datetime_series = pd.to_datetime(excel["Date"][1:], format="%df/%m/%Y")

                timestamps = datetime_series.apply(lambda x: x.timestamp())
            elif "Timestamp" in excel.columns:  # New format from json data in chart
                timestamps = excel["Timestamp"][1:]
            else:
                raise ValueError(
                    "The following Yahoo data file has an unsupported format: \n"
                    + fpath
                    + "\n"
                    + "If this file type should be supported, implement it in: \n"
                    + self.script_location
                )

            # Convert time to iShares format
            self.orig_index_tick_time = self.convert_time(np.array(timestamps), time_form="Generic")

            # Extract return series
            orig_return = np.array(excel["Adj Close"][1:], dtype=float)

            self.index_currency = excel["Currency"][0]

        elif fpath.find("MSCI") != -1 and file_ext == ".xlsx":
             # Read xlsx file
            excel = pd.read_excel(fpath)

            time = excel["Unnamed: 0"][5:]
            timestamps = pd.to_datetime(time, format='%Y-%m-%d').apply(lambda x: x.timestamp())

            # Convert time to iShares format
            self.orig_index_tick_time = self.convert_time(np.array(timestamps), time_form="Generic")

            # Extract return series
            orig_return = np.array(excel["Unnamed: 1"][5:], dtype=float)

            self.index_currency = excel["Unnamed: 1"][2]
        else:
            raise ValueError(
                "The following data file has been found but is not supported: \n"
                + fpath
                + "\n"
                + "If this file type should be supported, implement it in: \n"
                + self.script_location
                + "\n\nCurrently, the only supported files are: \n"
                + "'*yahoo.csv'"
            )

        # Remove NaNs
        valid_entries = ~np.isnan(orig_return)
        orig_return = orig_return[valid_entries]
        self.orig_index_tick_time = self.orig_index_tick_time[valid_entries]

        file_name = os.path.basename(fpath).split('/')[-1]
        if "Gold" in file_name:
            index = np.argmin(np.abs(self.orig_index_tick_time - 22720))
            orig_return = orig_return[:index]
            self.orig_index_tick_time = self.orig_index_tick_time[:index]

        ## Interpolate data to full dataset
        # (interpolation is done so the return can be calculated on all data and sampling
        # biases are removed)
        self.index_tick_time = np.arange(self.orig_index_tick_time[0], self.orig_index_tick_time[-1]+1, 1, dtype=int)
        # Perform interpolation (pchip is used for most accurate interpolation, without overshooting)
        self.index_return_series = PchipInterpolator(self.orig_index_tick_time, orig_return)(
            self.index_tick_time
        )

        return

    def __apply_fx(self, fx_df):

        # Extract fx rates for security and index
        if "GBP" not in self.currency:
            fx_timestamps, fx_rate = self.__extract_fx(self.currency, fx_df)
            sec_conversion = True
        else:
            sec_conversion = False
            fx_timestamps = []
            fx_rate = []

        has_index = hasattr(self, "index_currency")

        if has_index and "GBP" not in self.index_currency:
            if self.currency == self.index_currency:
                fx_index_timestamps = fx_timestamps.copy()
                fx_index_rate = fx_rate.copy()
            else:
                fx_index_timestamps, fx_index_rate = self.__extract_fx(self.index_currency, fx_df)
            index_conversion = True
        else:
            index_conversion = False
            fx_index_timestamps = []
            fx_index_rate = []

        if sec_conversion or index_conversion:

            # Find the inner-most start and end tick
            if sec_conversion:
                start_tick = max(self.tick_time[0], fx_timestamps[0])
                end_tick = min(self.tick_time[-1], fx_timestamps[-1])
            else:
                start_tick = self.tick_time[0]
                end_tick = self.tick_time[-1]

            if index_conversion:
                index_start_tick = max(self.index_tick_time[0], fx_index_timestamps[0])
                # Use a different end tick for the index in case it does not have as recent data as
                # the security. This should not limit the main security time series.
                index_end_tick = min(self.index_tick_time[-1], fx_index_timestamps[-1])
            elif has_index:
                index_start_tick = self.index_tick_time[0]
                index_end_tick = self.index_tick_time[-1]

            # Limit series by the new start and end date for which there is data
            self.tick_time, self.return_series = self.__slice_by_ticks(
                self.tick_time,
                self.return_series,
                start_tick=start_tick,
                end_tick=end_tick,
            )
            self.orig_tick_time = self.__slice_by_ticks(
                self.orig_tick_time,
                start_tick=start_tick,
                end_tick=end_tick,
            )
            if has_index:
                self.index_tick_time, self.index_return_series = self.__slice_by_ticks(
                    self.index_tick_time,
                    self.index_return_series,
                    start_tick=index_start_tick,
                    end_tick=index_end_tick,
                )
                self.orig_index_tick_time = self.__slice_by_ticks(
                    self.orig_index_tick_time,
                    start_tick=index_start_tick,
                    end_tick=index_end_tick,
                )

            # Apply FX rates
            if sec_conversion:
                fx_timestamps, fx_rate = self.__slice_by_ticks(
                    fx_timestamps,
                    fx_rate,
                    start_tick=start_tick,
                    end_tick=end_tick,
                )

                # Assumes there are ticks for all days within the time limits
                if len(fx_rate) != len(self.return_series):
                    raise ValueError(
                        "There are gaps in the timeseries of either the fx rate or return series,"
                        " despite the fact that they have both been interpolated.\n"
                        f"Length fx_rate: {len(fx_rate)}. Length return_series: {len(self.return_series)}"
                    )
                self.return_series *= fx_rate

            if index_conversion:
                fx_index_timestamps, fx_index_rate = self.__slice_by_ticks(
                    fx_index_timestamps,
                    fx_index_rate,
                    start_tick=index_start_tick,
                    end_tick=index_end_tick,
                )

                if len(fx_index_rate) != len(self.index_return_series):
                    raise ValueError(
                        "There are gaps in the timeseries of either the fx rate or return series,"
                        " despite the fact that they have both been interpolated.\n"
                        f"Length fx_index_rate: {len(fx_index_rate)}. Length index_return_series: {len(self.index_return_series)}"
                    )

                self.index_return_series *= fx_index_rate
        return

    def __slice_by_ticks(self, *arrays, start_tick, end_tick):
        if len(arrays) not in {1, 2}:
            raise ValueError("Expected one or two arrays to slice.")

        mask = (arrays[0] >= start_tick) & (arrays[0] <= end_tick)

        if len(arrays) == 1:
            return arrays[0][mask]

        return tuple(arr[mask] for arr in arrays)

    def __extract_fx(self, currency, fx_df):

        fx = BASE_CURRENCY + "-" + currency

        currency_fpath = fx_df["Currency_loc"][fx_df["Currency"] == fx].iloc[0]

        fpath = os.path.realpath(
            os.path.join(self.folder, "..", "fx", currency_fpath)
        )

        excel = pd.read_csv(fpath, header=None)

        # Extract the date at the end of the line (e.g. '02 Jul 26') using regex
        date_str = excel[0].astype(str).str.extract(r'(\d{1,2}\s+\w+\s+\d{2})$')[0]

        # Drop header/empty rows and strip whitespace
        date_str = date_str.dropna().str.strip()

        # Parse with day-first two-digit year
        timestamps = pd.to_datetime(date_str, format="%d %b %y", dayfirst=True, errors="coerce").apply(lambda x: x.timestamp())

        orig_fx_timestamps = self.convert_time(np.array(timestamps), time_form="Generic")[::-1]

        # The BoE rates are listed as GBP to something else, but we want it the other way round.
        orig_fx_rate = 1 / np.asarray(excel[1][1:], dtype=float)[::-1]

        fx_timestamps = np.arange(orig_fx_timestamps[0], orig_fx_timestamps[-1]+1, 1, dtype=int)
        # Perform interpolation (pchip is used for most accurate interpolation, without overshooting)
        fx_rate = PchipInterpolator(orig_fx_timestamps, orig_fx_rate)(
            fx_timestamps
        )
        return fx_timestamps, fx_rate


    def convert_time(self, time_array, time_form="iShares"):
        # time_array needs to be a numpy array
        # could implement input parser

        if time_form == "iShares":
            # dd/mm(m)/yyyy

            # Array with conversion of month with corresponding ticks from the previous months,
            # the first row is for a normal year, the second for a leap year (Sept is not included)
            month_ticks = np.array(
                [
                    [0, 31, 59, 90, 120, 151, 181, 212, 273, 304, 334],
                    [0, 31, 60, 91, 121, 152, 182, 213, 274, 305, 335],
                ]
            )

            # The abbrev. of the months used in the iShares files (Sept not included as it
            # is inconsistent with the others)
            month_list = np.array(
                ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Oct", "Nov", "Dec"]
            )

            # Function to convert from the month abbrev. to the corresponding tick number
            month_conv = lambda x: (
                month_ticks[0, x[3:6] == month_list]
                if int(x[7:]) % 4
                else month_ticks[1, x[3:6] == month_list]
            )

            # Function to convert Sept to the tick number for the leap and non-leap years
            month_conv_sep = lambda x: np.asarray([243]) if int(x[8:]) % 4 else np.asarray([244])

            # Function calculating the number of ticks for a given year, multiple of groups of 4 years
            # (i.e. one loop of the leap-year cycle) plus the remaining non-leap years
            year_conv = lambda x, y_ind: (
                ((int(x[y_ind:]) - self.zero_point - 1) // 4) * 1461
                + ((int(x[y_ind:]) - self.zero_point - 1) % 4) * 365
            )

            # Combining the functions above, to add the days, months and years and loop through all entries
            tick_time = np.asarray(
                [
                    int(date[:2])
                    + (
                        year_conv(date, 8) + month_conv_sep(date)
                        if date[3:7] == "Sept"
                        else year_conv(date, 7) + month_conv(date)
                    )
                    for date in time_array
                ],
                dtype=int,
            )[:, 0]

        elif time_form == "Generic":
            # Turn the datetime ticks into date ticks and add the offset to be consistent with iShares format
            datetime_ticks = np.empty_like(time_array, dtype=int)

            np.floor(time_array / 86400, out=datetime_ticks, casting="unsafe")

            tick_time = datetime_ticks + self.convert_time(
                np.array(["01/Jan/1970"]), time_form="iShares"
            )
        else:
            raise ValueError(f"The provided time_form is not supported: {time_form}\n")
        return tick_time

    def generate_intervals(self, months=[]):

        # Set a default array with the month intervals to use
        if np.shape(months)[0] == 0:
            yrs = 7
            months = np.append(
                np.arange(6, 12, 2, dtype=int), np.arange(12, yrs * 12, 8, dtype=int)
            )

        month_ticks = np.asarray(months * 365.25 / 12, dtype=int)

        valid_months = month_ticks < (self.tick_time[-1] - self.tick_time[0])
        month_ticks = month_ticks[valid_months]
        months = months[valid_months]

        # Return the calculated intervals, using the average month length in a year
        return months, month_ticks

    def calc_return_matrix(self, months, start_date=None):

        self.months, t_int = self.generate_intervals(months)

        _, tick_time, return_series = self._set_start_tick(start_date)

        int_len = len(t_int)
        t_len = len(tick_time)

        # Extract indices from the ticks:
        indices = (
            tick_time - tick_time[0]
        )  # As all points are a full set of integers from the start date to now
        index_mx = np.tile(indices, (int_len, 1))  # Convert into matrix
        index_mx += np.tile(t_int, (t_len, 1)).T  # Add time intervals to matrix

        # Setting too large indices to mask (at the end of the return series, you can't
        # calculate the delta anymore i.e. 1 month return 0.5 months before the end of the series).
        # The indices for these non-calculable points are set to zero for now and then set to nan after
        mask = index_mx > t_len - 1
        index_mx[mask] = 0

        # Creating the y matrix based on the index matrix
        y_mx = return_series[index_mx]
        y_mx[mask] = np.nan

        # Calculate the deltas (the returns)
        y_mat = np.tile(return_series, (int_len, 1))
        dy_mx = y_mx - y_mat
        rel_dy_mx = dy_mx / y_mat

        return rel_dy_mx

    def _set_start_tick(self, start_date=None):
        # Set the data start date:
        if start_date == None:
            start_tick = self.tick_time[0]
            tick_time = self.tick_time.copy()
            return_series = self.return_series.copy()
        else:
            # Convert string format start_date to tick with the zero_point
            tick_form_delta = self.convert_time(np.array(["01/Jan/1970"]), time_form="iShares")
            start_tick = int(
                np.floor(
                    (datetime.datetime.strptime(start_date + " 01", "%d/%m/%Y %H").timestamp())
                    / 86400
                )
                + tick_form_delta
            )
            # Note, the hour needed to be added because of the timestamp datetime generates for a simple date

            # Slice the arrays to use the start_index
            start_index = np.argmin(abs(self.tick_time - start_tick))
            tick_time = self.tick_time[start_index:]
            return_series = self.return_series[start_index:]
        return start_tick, tick_time, return_series

    def plot_security(self, std_mult=[1, 2, 3], limit=2, time_index=-1, months=[], which="all"):

        # Convert starting tick to string:
        tick_form_delta = self.convert_time(np.array(["01/Jan/1970"]), time_form="iShares")[0]
        start_date = datetime.datetime.fromtimestamp(
            (self.tick_time[0] - tick_form_delta) * 86400
        ).date()

        if which == "all" or which == "future":
            if len(months) == 0:
                months = self.months

            if not hasattr(self, "return_matrix"):
                self.return_matrix = self.calc_return_matrix(months)

            # Calculate statistics
            self.std_array, self.std_err = self.calc_std_1D(self.return_matrix, months)

            # Generate Statistics and Future estimate plots
            title = f"Return estimation based on historic data in {BASE_CURRENCY} ({start_date}+): {self.name}"
            self.future_plot(
                self.std_array,
                self.std_err,
                self.return_matrix * 100,
                months,
                title,
                std_mult,
                limit,
                time_index=time_index,
            )

        if which == "all" or which == "historic":

            # Generate backtracing model data
            if len(self.backtracing) == 0:
                backtrace_factor_series = []
                backtrace_series = []
            else:
                backtrace_factor_series = self.evaluate_bare_model(
                    self.index_tick_time, self.backtracing["Parameters"], self.backtracing["Model type"]
                )
                backtrace_series = self.evaluate_model(
                    self.index_return_series, self.index_tick_time, self.backtracing["Parameters"], self.backtracing["Model type"]
                )

            # Generate historic time series plot
            title = f"Historic return data in {BASE_CURRENCY} ({start_date}+): {self.name}"
            self.historic_plot(
                return_series=self.return_series,
                tick_time=self.tick_time,
                orig_tick_time=self.orig_tick_time,
                index_return_series=self.index_return_series,
                index_tick_time=self.index_tick_time,
                orig_index_tick_time=self.orig_index_tick_time,
                security_start_tick=self.inception_tick,
                backtrace_factor_series=backtrace_factor_series,
                backtrace_series=backtrace_series,
                backtrace_params=self.backtracing,
                title_input=title,
            )

        return

    def save_security(
        self,
        saving_loc=os.path.realpath(os.path.join(script_location, "..", "..", "data", "pickles")),
    ):

        file_loc = os.path.join(saving_loc, self.name.replace(" ", "_") + ".pkl")

        with open(file_loc, "wb") as file:
            pickle.dump(self, file, pickle.HIGHEST_PROTOCOL)

        return
