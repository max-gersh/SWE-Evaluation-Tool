from datetime import datetime
from pathlib import Path
import os
import numpy as np

from src import BASE_DIR

## Function to create report directories
def create_report_dirs(report_date):
    """
    Creates report folder for date with csvs, figures, and pdfs subdirectories.

    Parameters:
        report_date (str): String of current report date.

    Returns:
        No return value
    """   
    report_date_formatted = datetime.strptime(report_date, "%Y%m%d").strftime("%Y-%m-%d")
    base = BASE_DIR / "reports" / report_date_formatted # base path for report
    subdirs = ['csvs', 'figures', 'pdfs', 'pkl']
    for i in range(len(subdirs)):
        folder = Path(base / subdirs[i])
        folder.mkdir(parents=True, exist_ok=True)
        print(f'Created directory: {folder}')


def last_report_date(date):
    """
    Searches "reports" folder to get last report date given current report date.

    Parameters:
        date (str): String object of the date of the report to be generated. 

    Returns:
        str: Returns a string object of the date of the last report; to be use for SWE difference calculation. 
    """

    current_date = datetime.strptime(date, "%Y%m%d").date()

    # get water year start and end from date
    if(current_date.month, current_date.day) >= (10, 1):
        wy_start = datetime(current_date.year, 10, 1).date()
        wy_end = datetime(current_date.year + 1, 9, 30).date()
    else:
        wy_start = datetime(current_date.year - 1, 10, 1).date()
        wy_end = datetime(current_date.year, 9, 30).date()    

    report_dirs = os.listdir(BASE_DIR / "reports") # list folders in 'reports' directory
    report_dirs = [d for d in report_dirs if d.startswith("20")] # filter to starting with "20"
    report_dates = [datetime.strptime(d, "%Y-%m-%d").date() for d in report_dirs] # convert to date objects
    
    ## get dates less than current date
    report_dates_filtered = [d for d in report_dates if d < current_date]
    ## get max date, convert to string
    if len(report_dates_filtered) > 0:
        max_date = max(report_dates_filtered).strftime("%Y-%m-%d")
    else: 
        max_date = np.nan    

    return(max_date)