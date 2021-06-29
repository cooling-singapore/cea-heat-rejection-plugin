"""
This tool creates building groups in CEA, used by the heat rejection model.
"""
import cea.config
import cea.inputlocator
import cea.plugin
import numpy as np
import pandas as pd
import geopandas as gpd
import csv
import os
import warnings

from itertools import groupby
from cea.utilities import epwreader
from cea.utilities.dbf import dbf_to_dataframe
from cea.utilities.date import get_date_range_hours_from_year
from cea.demand import demand_writers

from cea_heat_rejection_plugin import BASE_CT_THRESHOLD
from cea_heat_rejection_plugin.utilities.DK_thermo import HumidAir
from cea_heat_rejection_plugin.utilities.coolingtowers import set_ambient, simulate_CT, parse_BldgToCTs, calc_CTheatload

__author__ = "Cooling Singapore (Luis Santos, Reynold Mok)"
__copyright__ = "Copyright 2020, Architecture and Building Systems - ETH Zurich"
__credits__ = ["Luis Santos, Reynold Mok, David Kayanan, Jimeno Fonseca"]
__license__ = "MIT"
__version__ = "1.0"
__maintainer__ = "Reynold Mok"
__email__ = "cea@arch.ethz.ch"
__status__ = "Production"

def main(config):

    """
    This tool creates building groups that can be used in the heat rejection model.
    For buildings that are NOT into a district system (according to the HVAC_SUPPLY databases), each building will be assigned to a different group.
    For buildings that are into a district system (according to the HVAC_SUPPLY databases), all of them will be assigned to a single group.
    """

    locator = cea.inputlocator.InputLocator(config.scenario, config.plugins)
    building_supply = dbf_to_dataframe(locator.get_building_supply())
    database_supply = pd.read_excel(locator.get_database_supply_assemblies(), "COOLING")

    # Check if the user included a building group in the inputs folder
    try:
        with open(locator.get_groups()):
            print("Building groups were previously defined. CEA will erase those files and create a new one.")

    # The building group is created automatically in the inputs folder if not provided by the user
    except IOError:
        print("Buildings groups not informed, CEA will consider individual buildings for each group (unless connected to District Cooling)")

    #Get list of CEA buildings, separated by decentralized or centralized (district cooling) systems
    names_decentralized = []
    names_centralized = []

    for i,row in building_supply.iterrows():
        # Buildings that have district cooling supply are assigned to a centralized list
        if database_supply.loc[database_supply.code == row.type_cs].scale.values == "DISTRICT":
            names_centralized.append(row.Name)
        # Buildings that have no district cooling supply are assigned to a decentralized list
        else:
            names_decentralized.append(row.Name)

    # Write CEA buildings groups into a group.csv file:
    locator._ensure_folder(locator.scenario, 'inputs', 'groups')
    with open(locator.get_groups(), 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(('Group', 'Buildings'))
        counter =0
        while counter < len(names_decentralized):
            group_name = 'G1' + str(counter).zfill(3)
            writer.writerow((group_name, names_decentralized[counter]))
            counter += 1
        if names_centralized:
            group_name = 'G1' + str(counter).zfill(3)
            writer.writerow((group_name, ",".join(names_centralized)))

    building_groups = pd.read_csv(locator.get_groups())
    print("Building groups: \n", building_groups) #print table with all groups of buildings

if __name__ == '__main__':
    main(cea.config.Configuration())
