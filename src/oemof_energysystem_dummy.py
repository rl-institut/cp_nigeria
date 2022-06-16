# # Energy system optimisation with oemof - CP Nigeria dummy system

# ### Import necessary modules

import os
import pandas as pd
import pprint as pp

import oemof.solph as solph
import oemof_visio as oev
from oemof.tools import economics
import pickle
import matplotlib.pyplot as plt

# ### Specify solver

solver = 'cbc'

# ### Create an energy system and optimize the dispatch at least costs.

# initialize and provide data
nr_timesteps = 24 * 365
datetimeindex = pd.date_range('1/1/2016', periods=nr_timesteps, freq='H')
energysystem = solph.EnergySystem(timeindex=datetimeindex)
filename = 'input_data.csv'
filename = os.path.join(os.getcwd(), filename)
data = pd.read_csv(filename, sep=",")

# ### Create and add components to energysystem

# Choose system components
STORAGE = True
PV = False

# add diesel and electricity busses
bus_el = solph.Bus(label='electricity')
bus_diesel = solph.Bus(label='diesel')

energysystem.add(bus_el, bus_diesel)

# add excess electricity variable
excess = solph.Sink(label='excess_el', inputs={bus_el: solph.Flow()})

# declare variables
# economic variables
epc_pv = economics.annuity(capex=1000, n=20, wacc=0.05)
epc_genset = economics.annuity(capex=800, n=20, wacc=0.05)
epc_storage = economics.annuity(capex=1000, n=20, wacc=0.05)
price_diesel = 0.04

# genset variables
existing_capacity_genset = 10
efficiency_genset = 0.33

# storage variables
existing_storage = 1000
loss_rate = 0.02
initial_storage_level = None
storage_crate_charge = 1 / 6
storage_crate_discharge = 1 / 6
storage_efficiency_charge = 1
storage_efficiency_discharge = 0.8

# add sources
if PV is True:
    pv = solph.Source(label='pv', outputs={bus_el: solph.Flow(
        fix=data['pv'], investment=solph.Investment(ep_costs=epc_pv))})
    energysystem.add(pv)

diesel_resource = solph.Source(label='rdiesel', outputs={bus_diesel: solph.Flow(
    variable_costs=price_diesel)})

# add transformers
genset = solph.Transformer(label='genset', inputs={bus_diesel: solph.Flow()}, outputs={bus_el: solph.Flow(
    investment=solph.Investment(ep_costs=epc_genset, existing=existing_capacity_genset))},
                           conversion_factors={bus_el: efficiency_genset},
                           )

# add storage
if STORAGE is True:
    storage = solph.components.GenericStorage(label='storage', investment=solph.Investment(ep_costs=epc_storage,
                                                                                           existing=existing_storage),
                                              inputs={bus_el: solph.Flow()},
                                              outputs={bus_el: solph.Flow()},
                                              loss_rate=loss_rate,
                                              initial_storage_level=None,
                                              invest_relation_input_capacity=storage_crate_charge,
                                              invest_relation_output_capacity=storage_crate_discharge,
                                              inflow_conversion_factor=storage_efficiency_charge,
                                              outflow_conversion_factor=storage_efficiency_discharge)
    energysystem.add(storage)

# add electricity demand
demand = solph.Sink(label='demand_el', inputs={bus_el: solph.Flow(
    nominal_value=85, fix=data['demand_el'])})  # nominal value and fix from data survey


# add components to energy system
energysystem.add(diesel_resource, genset, demand, excess)

gr = oev.ESGraphRenderer(energy_system=energysystem, filepath="energy_system", img_format="png")
gr.view()

# ### Optimization

# create optimization model based on energy_system
optimization_model = solph.Model(energysystem=energysystem)

# solve problem
optimization_model.solve(solver=solver,
                         solve_kwargs={'tee': True, 'keepfiles': False})

##########################################################################
# Check and plot the results
##########################################################################

# check if the new result object is working for custom components
results = solph.processing.results(optimization_model)

electricity_bus = solph.views.node(results, "electricity")

meta_results = solph.processing.meta_results(optimization_model)
pp.pprint(meta_results)

my_results = electricity_bus["scalars"]

# installed capacity of storage in GWh
if STORAGE is True:
    custom_storage = solph.views.node(results, "storage")
    my_results["storage_invest_GWh"] = (
            results[(storage, None)]["scalars"]["invest"] / 1e6
    )

# installed capacity of wind power plant in MW
if PV is True:
    my_results["pv_invest_MW"] = results[(pv, bus_el)]["scalars"]["invest"] / 1e3

# resulting renewable energy share
my_results["res_share"] = (
        1
        - results[(genset, bus_el)]["sequences"].sum()
        / results[(bus_el, demand)]["sequences"].sum()
)

pp.pprint(my_results)

# Make a smooth plot even though it is not scientifically correct.
cdict = {
    (("electricity", "demand"), "flow"): "#ce4aff",
    (("electricity", "excess"), "flow"): "#5b5bae",
    (("genset", "electricity"), "flow"): "#636f6b",
}

if PV is True:
    cdict[(("pv", "electricity"), 'flow')] = "#ffde32"

if STORAGE is True:
    cdict[(("electricity", "storage"), "flow")] = "#42c77a"
    cdict[(("storage", "electricity"), "flow")] = "#42c77a"

electricity_seq = solph.views.node(results, "electricity")["sequences"]

ax = electricity_seq.plot(kind='line', drawstyle='steps-post', figsize=(10, 5))
ax.set_xlabel('Time')
ax.set_ylabel('Energy [MWh]')
ax.set_xlim([electricity_seq.index[0], electricity_seq.index[int(len(electricity_seq) / 12)]])  # plot only january
ax.set_title('Flows into and out of bel')
ax.legend()
plt.show()

# ### Save results - Dump the energysystem (to ~/home/user/.oemof by default)
# Specify path and filename if you do not want to overwrite

# energysystem.dump(dpath=None, filename=None)
