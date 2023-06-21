# cea-heat-rejection
This CEA plugin is used to generate results of heat rejection, which are also divided between sensible and latent heat forms.
Heat rejection is defined as the total heat that leaves the building through air-conditioning, which includes the cooling load and the energy required by cooling systems.

As preparation, the user may want to include building groups in case buildings are connected to a common heat rejection points. 
The file is located in ```project/scenario/inputs/groups/group.csv``` and must contain a column (named Group) with group IDs (starting with G1000), and a second columns (named Buildings) with the buildings ID in CEA that correspond to the respective group, separated by commas.
Examples are podium connected to towers (with a common cooling tower system) or buildings connected to the same district cooling plant.
Alternativelly, the buildings groups can be generated automatically via the 'Groups Helper' (located in groups_helper.py) script.
The groups helper script will generated building groups with each building being assigned to a specfific group ID, except if they are connected to a distrct supply system. In this case, a single group ID is created for all the buildings in this category.

The 'Heat Rejection' script (located in heat_rejection.py) creates outputs of hourly heat that is rejected by each building group (previously assigned or created with 'Group Helper').
In case the group system is defined by a wet cooling tower, the model splits the heat rejected into sensible and latent fractions. For the remaining cases, heat is assumed to be 100% sensible heat.

## Installation 
To install, clone this repo to a desired path (you would need to have `git` installed to run this command. Alternatively you can also run this command in the CEA console, which
comes with `git` pre-installed):

```git clone https://github.com/architecture-building-systems/cea-plugin-template.git DESIRED_PATH```


Open CEA console and enter the following command to install the plugin to CEA:

```pip install -e PATH_OF_PLUGIN_FOLDER``` 

or 

```python -m pip install -e PATH_OF_PLUGIN_FOLDER``` 

(NOTE: PATH_OF_PLUGIN_FOLDER would be the DESIRED_PATH + 'cea-template-plugin')


In the CEA console, enter the following command to enable the plugin in CEA:

```cea-config write --general:plugins cea_heat_rejection_plugin.heat_rejection.HeatRejectionPlugin```

NOTE: When installing multiple plugins, add them as a comma separated list in the `cea-config write --general:plugins ...` command.
