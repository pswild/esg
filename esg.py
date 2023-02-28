# -*- coding: utf-8 -*-
#!/usr/bin/env python3

"""
Simulate baseline operation of ESG.

Created on Mon Feb 27 14:21:51 2022

@author: pswild
"""

import os
import numpy as np
import pandas as pd

#--- PATH ---# 

here = os.path.dirname(os.path.realpath(__file__))

#--- DATA ---#

supply_file = os.path.join(here, 'data/supply.csv')
demand_file = os.path.join(here, 'data/demand.csv')

# Hourly cost by portfolio.
hrly_costs = {
    'Bay_Views': -5500,
    'Beachfront': -6750,
    'Big_Coal': -5000,
    'Big_Gas': -2000,
    'East_Bay': -4000,
    'Fossil_Light': -9250,
    'Old_Timers': -11250
}

#--- OUTPUT ---#

output_file = os.path.join(here, 'output/output.csv')

#--- FUNCTIONS ---#

def summarize_portfolios(supply):

    # Define weighted average.
    weighted = lambda x: np.average(x, weights=supply.loc[x.index, 'mw'])
    
    # Group by portfolio. 
    portfolios = supply.groupby('portfolio_name', as_index=False).agg(agg_cap=('mw', 'sum'), agg_fixom=('fixom', 'sum'), wa_vom=('mc', weighted))
    
    return

def simulate(supply, demand, offset=0):

    # Hourly stats. 
    hourly = pd.DataFrame()

    for _, period in demand.iterrows():

        # Period. 
        day = period['day']
        hour = period['hour']
        load = period['load']

        # print('Day, ', day)
        # print('Hour ', hour)
        # print('Load ', load)

        # Dispatch instance. 
        dispatch = supply.copy()

        # Flag for inframarginal.
        dispatch['inframarginal'] = False

        # Flag for marginal. 
        dispatch['marginal'] = False

        # Set generation to zero.
        dispatch['gen'] = 0

        # Set revenue to zero. 
        dispatch['revenue'] = 0

        # Index of marginal unit.
        marginal = len(dispatch.loc[dispatch['cumulative'] < load])

        # Identify inframarginal units.
        dispatch.loc[:marginal - 1, 'inframarginal'] = True

        # Identify marginal unit.
        dispatch.loc[marginal, 'marginal'] = True

        # Update generation. 
        dispatch.loc[dispatch['inframarginal'], 'gen'] = dispatch['mw']
        dispatch.loc[dispatch['marginal'], 'gen'] = dispatch['mw'] - (dispatch['cumulative'] - load)
        
        # Calculate clearing price under zero profit condition. 
        cp = dispatch.loc[marginal]['mc'] + offset

        # Calculate revenue for each unit. 
        dispatch['revenue'] = dispatch['gen'] * (cp - dispatch['mc'])

        # Calculate revenue for each portfolio.
        portfolios = dispatch.groupby('portfolio_name', as_index=False).agg({'revenue': 'sum'})

        # Map hourly cost onto each portfolio.
        portfolios['cost'] = portfolios['portfolio_name'].map(hrly_costs)

        # Calculate profit for each portfolio. 
        portfolios['profit'] = portfolios['revenue'] + portfolios['cost']

        # Add period identifiers. 
        portfolios['day'] = day
        portfolios['hour'] = hour

        # Reformat.
        portfolios = portfolios[['day', 'hour', 'portfolio_name', 'revenue', 'cost', 'profit']]

        # Add to hourly stats.
        hourly = pd.concat([hourly, portfolios])

    # Group by day. 
    daily = hourly.groupby(['day', 'portfolio_name'], as_index=False).agg({'profit': 'sum'})

    # Group by portfolio.
    aggregate = daily.groupby(['portfolio_name'], as_index=False).agg({'profit': 'sum'})

    # Sort by profit.
    aggregate = aggregate.sort_values(by=['profit'], ascending=False)

    return aggregate

if __name__ == '__main__':
    
    #--- DATA ---

    supply = pd.read_csv(supply_file)
    demand = pd.read_csv(demand_file)

    #--- PORTFOLIOS ---#
    
    summarize_portfolios(supply)

    #--- SIMULATION ---#

    # Output. 
    output = None

    # Calculate baseline profit by portfolio.
    baseline = simulate(supply, demand, 0)

    # Rename profit column. 
    baseline = baseline.rename(columns={'profit': 'MC'})

    # Update output. 
    output = baseline

    for offset in range(1, 21):

        # Calculate change in profits under exogenous increase in clearing price.
        new_profit = simulate(supply, demand, offset)

        # Rename profit column. 
        new_profit = new_profit.rename(columns={'profit': '$' + str(offset)})

        # Merge on porfolio name. 
        output = output.merge(new_profit, on='portfolio_name')

    # Write output to CSV.
    output.to_csv(output_file, index=False)

    print(output)
