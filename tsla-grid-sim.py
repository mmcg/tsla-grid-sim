# A sanity check on Tesla's energy generation numbers.  See tsla-grid.md.
# This started as a quick hack, then grew.  Don't expect quality code.
import csv, os, graphlib
import numpy as np

EIA_DATA_DIR = 'eia-data'

# The big US regions
EIA_REGIONS = {
    'Western': ['NW', 'CAL', 'SW'],
    'Central': ['CENT', 'MIDW'],
    'Texas':   ['TEX'],
    'Eastern': ['NE', 'NY', 'MIDA', 'TEN', 'SE', 'FLA', 'CAR'],
    'Lower48': ['US48']
}
EIA_REGIONS['CentralAndEastern'] = EIA_REGIONS['Central'] + EIA_REGIONS['Eastern']
EIA_REGIONS['All'] = EIA_REGIONS['CentralAndEastern'] + EIA_REGIONS['Texas'] + EIA_REGIONS['Western'] # should match US48

HOURS_PER_YEAR = 24 * 365

# The first 6 months of disaggregated EIA reporting has some egregious errors (it looks
# like some of the BAs took that long to sort out their IT problems - at a minimum: BPAT,
# GRID, NWMT).  So we can set a start year.
START_AT_YEAR = 2019

# Discounted capacity factors, from tesla's paper.  "Discounted" means "after curtailment".
# It's unclear how useful post-curtailment figures are here.
TSLA_WIND_DCF = .352
TSLA_SOLAR_DCF = .151

# Overbuild: Tesla says 32%, but I calculated 28% for wind+solar (from their generation table).
# 32/28 = 1.14, so this might be where they built in their 15% safety margin.
TSLA_OVERBUILD = 0.32

# 2035:3052 is suspiciously close to 40:60
TSLA_WIND_PERCENTAGE = 0.4

# hours of levelised demand drawdown before blackouts happen
TSLA_STORAGE_HOURS = 120 / 11637 * HOURS_PER_YEAR

class ParameterBase(object):
    def __init__(self, overrides=None):
        for k, v in self.parameter_defaults().items():
            setattr(self, k, v[0])
        self.set_parameters(self.parameter_overrides())
        if overrides:
            self.set_parameters(overrides)

    def set_parameters(self, params):
        for k, v in params.items():
            try:
                getattr(self, k)
                setattr(self, k, v)
            except:
                raise Exception(f'Unknown parameter: {k} - value: {v}')

    def print_parameters(self):
        for k, p in self.parameter_defaults().items():
            if p[1]:
                print(f'    {k}: {p[1](getattr(self,k))}')
            else:
                print(f'    {k}: {getattr(self,k)}')

# Simulation parameters
class SimParams(ParameterBase):
    def __init__(self, fname, overrides=None):
        self.filename = fname
        super().__init__(overrides)

    def print_parameters(self):
        print(f'Parameters:')
        print(f'    Data: {self.filename}')
        super().print_parameters()

    def parameter_overrides(self):
        # Uncomment the ones you want to change (they are set to a
        # sensible non-default) - or add new ones.
        return {
            # 'cf_filter_duration': 24 * 7 * 16,
            # 'min_historical_cf': 0, # don't filter any historical low-renewables ranges (useful for GridWatch)
            # 'storage_hours': 10,
            # 'isolate_region': True,
            # 'capacity_planning_lookahead': 0, # No lookahead
            # 'capacity_planning_lookahead': HOURS_PER_YEAR // 4, # 3 months
            # 'capacity_planning_percentile': 0, # use levelised rather than peak
            # 'overbuild': 0,
            # 'calculate_dcf': False,
            # 'wind_dcf': TSLA_WIND_DCF,
            # 'solar_dcf': TSLA_SOLAR_DCF,
            # 'optimise_wind_fraction': False,
            # 'default_wind_fraction': 0.75,

            ## Eliminate nuclear and hydro as well:
            # 'keep_generators': [],
            #
            ## Keep just hydro:
            # 'keep_generators': [HYDRO_COL],
            #
            ## Keep all generators, just resize renewables.
            # 'keep_generators': [i for i in range(len(eia_cols)) if eia_cols[i] in keep_gen + fossil_gen ],
        }

    def parameter_defaults(self):
        # Default parameter values, and functions to pretty-print them.
        # Adjust these in parameter_overrides().
        return {
            # Lots of regions are missing either wind or solar - we can't simulate them - and
            # some individual producers have assets that disappear for long periods.  We
            # will ignore datapoints for which either wind or solar has run at less than
            # 2% of its calculated historical capacity factor for at least the surrounding 3 weeks.
            'cf_filter_duration': (24 * 7 * 3, None),
            'min_historical_cf': (0.02, None),

            # How much storage we will install.  Depleting storage causes blackouts, which are tracked and summarised.
            'storage_hours': (TSLA_STORAGE_HOURS, None),

            # If true, then set the region's electricity imports/exports to zero - we must cover
            # net imports with local renewables, but no longer need to generate exports.
            'isolate_region': (False, None),

            # We assume that the historical installed generation capacity (at any given moment) matches
            # the highest power output we have previously seen.  To smooth out the early estimates, we
            # can also look ahead.  This lookahead also applies to demand (used to size new generation).
            # 0-12 months is reasonable.
            'capacity_planning_lookahead': (HOURS_PER_YEAR, lambda i: f'{i/24} days'),

            # Usually, we size the base installed generation capacity to match the maximum previously observed
            # demand for renewables (as modified by capacity_planning_lookahead).  We can instead size it against
            # levelised demand.  Here, 0=levelised, 1=maximum, and you can set any fraction in between.
            'capacity_planning_percentile': (1, None), # maximum

            # Once we have chosen a base capacity, we overbuild by some fraction.  0.5 means add 50%.
            # If negative, underbuild.
            'overbuild': (TSLA_OVERBUILD, None),

            # Usually we assume the levelised capacity factors of the new equipment will match
            # those estimated from the historical equipment.  If calculate_dcf is False, we will
            # instead use the wind_dcf and solar_dcf specified here.
            'calculate_dcf': (True, None),
            'default_wind_dcf': (TSLA_WIND_DCF, None),
            'default_solar_dcf': (TSLA_SOLAR_DCF, None),

            # By default we choose a wind fraction which will minimise the maximum drawdown.
            # If optimise_wind_fraction is False, we will assume 40% wind, 60% solar.
            'optimise_wind_fraction': (True, None),
            'default_wind_fraction': (TSLA_WIND_PERCENTAGE, None),

            # Sets the list of generation types that should be retained.  By default we keep
            # nuclear and hydroelectric; everything else is replaced by wind and solar.
            'keep_generators': ([i for i in range(len(eia_cols)) if eia_cols[i] in keep_gen ],
                                lambda g: f'{g} - {[eia_cols[i] for i in g]}'),
        }
    
def simulate(basedata, params, slots_per_hour, timestamps, quiet=False):
    '''Runs generation and storage against historical data, replacing any generators
    not listed in `params.keep_generators` with renewable resources.'''
    year_slots = HOURS_PER_YEAR * slots_per_hour
    lookahead_slots = params.capacity_planning_lookahead * slots_per_hour
    # Uncomment to consider just the last 2 years:
    # basedata = basedata[:, -year_slots*2:]; timestamps = timestamps[-year_slots*2:]
    data = basedata.copy()
    data[FIRST_GEN_COL:][data[FIRST_GEN_COL:] < 0] = 0
    # Check whether a simulation is even possible (we can't get capacity factors for the region
    # unless we have both).  We will only include datapoints where wind and solar have each
    # averaged more than 2% of their nameplate generation in the surrounding several weeks.  If
    # that leaves less than a year of data overall, we're screwed anyway (levelised calcs fail).
    missing_window_len = params.cf_filter_duration * slots_per_hour
    adequate_wind_gen = centered_sma(data[WIND_COL], missing_window_len) > np.maximum.accumulate(data[WIND_COL]) * params.min_historical_cf
    adequate_solar_gen = centered_sma(data[SOLAR_COL], missing_window_len) > np.maximum.accumulate(data[SOLAR_COL]) * params.min_historical_cf
    adequate_gen = adequate_wind_gen & adequate_solar_gen
    num_adequate_slots = np.count_nonzero(adequate_gen)
    if num_adequate_slots < year_slots * 1.5:
        print(f'{params.filename}: insufficient renewables datapoints')
        return None
    # Save timestamps for discarded ranges (only for printing).
    agi = np.nonzero(adequate_gen[1:] != adequate_gen[:-1])[0]
    if not adequate_gen[0]:
        agi = np.insert(agi, 0, 0)
    discarded_ranges = [(j-i, timestamps[i], timestamps[j]) for i, j in zip(agi[::2], agi[1::2])]
    data = data[:, adequate_gen]
    timestamps = [ timestamps[i] for i, t in enumerate(adequate_gen) if t]
    # OK, good to go.  Sum up all of the contributions we're keeping.
    data_rows, data_hours = data.shape
    nonrenewables_contribution = np.sum(data[params.keep_generators, :], axis=0)
    if not params.isolate_region:
        nonrenewables_contribution -= data[EXPORT_COL] # negative numbers are power imports
    required_renewables = data[DEMAND_COL] - nonrenewables_contribution
    required_renewables[required_renewables < 0] = 0
    # Work out max and rolling average renewables demand
    levelised_required_renewables = centered_sma(required_renewables, year_slots, year_slots)
    max_levelised_required = np.maximum.accumulate(levelised_required_renewables)
    max_nonlevelised_required = np.maximum.accumulate(required_renewables)
    if lookahead_slots:
        max_levelised_required[:-lookahead_slots] = max_levelised_required[lookahead_slots:]
        max_levelised_required = np.maximum.accumulate(max_levelised_required, axis=-1)
        max_nonlevelised_required[:-lookahead_slots] = max_nonlevelised_required[lookahead_slots:]
        max_nonlevelised_required = np.maximum.accumulate(max_nonlevelised_required, axis=-1)
    max_required = params.capacity_planning_percentile * max_nonlevelised_required + (1 - params.capacity_planning_percentile) * max_levelised_required
    # Observed historical max power outputs and discount factors
    historical_maxes = np.maximum.accumulate(data, axis=1)
    if lookahead_slots:
        historical_maxes[:, :-lookahead_slots] = historical_maxes[:, lookahead_slots:]
        historical_maxes = np.maximum.accumulate(historical_maxes, axis=1)
    cap_factors = np.divide(data, historical_maxes, out=np.zeros_like(historical_maxes), where=historical_maxes!=0)
    levelised_wind_dcf = max(np.average(cap_factors[WIND_COL, :]), 0.001) # uncurtailed
    levelised_solar_dcf = max(np.average(cap_factors[SOLAR_COL, :]), 0.001)
    if params.calculate_dcf:
        wind_dcf = levelised_wind_dcf # uncurtailed
        solar_dcf = levelised_solar_dcf
    else:
        wind_dcf = params.default_wind_dcf
        solar_dcf = params.default_solar_dcf
    
    # This function is returned for use by the optimiser
    def calc_parameterised(wind_fraction, overbuild):
        # Generation will be sized based on the maximum prior supply deficit (max_required).
        max_overbuilt = max_required * (1 + overbuild)
        wind_nameplate = (wind_fraction / wind_dcf) * max_overbuilt
        solar_nameplate = ((1 - wind_fraction) / solar_dcf) * max_overbuilt
        renewables_levelised = wind_nameplate * wind_dcf + solar_nameplate * solar_dcf # levelised annual output at each hour
        # Power output based on historical weather
        renewables_contribution = wind_nameplate * cap_factors[WIND_COL] + solar_nameplate * cap_factors[SOLAR_COL]
        generated = nonrenewables_contribution + renewables_contribution
        oversupply = generated - data[DEMAND_COL]
        storage_hours_generated = oversupply / renewables_levelised # per hour
        cum_storage = np.cumsum(storage_hours_generated)
        return (wind_nameplate, solar_nameplate, storage_hours_generated, cum_storage)

    if not quiet:
        wind_frac = params.default_wind_fraction
        if params.optimise_wind_fraction:
            wind_frac = optimise_wind_frac(calc_parameterised, params.overbuild)
        (wind_nameplate, solar_nameplate, storage_hours_generated, cum_storage
        ) = calc_parameterised(wind_frac, params.overbuild)
        
        max_drawdown, dd_start, dd_end = get_max_drawdown(cum_storage)
        # We used to simulate a battery with a loop, but enumerating drawdowns makes a lot more sense.
        # Unfortunately we lose the "curtailed" calculation.
        half_drawdowns = get_drawdowns(cum_storage, max_drawdown / 2.0)
        depletion = []
        blackout_slots = 0
        for _, s, e in get_drawdowns(cum_storage, params.storage_hours * slots_per_hour):
            bs = s + np.argmax(cum_storage[s] - cum_storage[s:e] >= params.storage_hours * slots_per_hour)
            depletion.append((timestamps[bs], timestamps[e]))
            blackout_slots += e - bs

        simulate_drawdowns = False

        if simulate_drawdowns:
            # No saturating arithmetic in numpy - have to loop.
            clipped_drawdown = 0 # in storage-hours
            curtailed_hours = 0
            blackout_start = None
            blackout_durations = []
            blackout_starts = []
            for i in range(data_hours):
                storage_hours = storage_hours_generated[i]
                clipped_drawdown += storage_hours
                if storage_hours >= 0:
                    if blackout_start is not None:
                        blackout_starts.append(i)
                        blackout_durations.append(i - blackout_start)
                        blackout_start = None
                    if clipped_drawdown > 0:
                        curtailed_hours += clipped_drawdown
                        clipped_drawdown = 0
                else:
                    if clipped_drawdown < -params.storage_hours * slots_per_hour:
                        if blackout_start is None:
                            blackout_start = i
                        clipped_drawdown = -params.storage_hours * slots_per_hour


        # Jarto wanted to see how much the existing capacity would be scaled up.
        final_wind_multiple = wind_nameplate[-1] / historical_maxes[WIND_COL, -1]
        final_solar_multiple = solar_nameplate[-1] / historical_maxes[SOLAR_COL, -1]

        params.print_parameters()
        print(f"Minimum storage required to avoid all blackouts (storage-hours): {max_drawdown/slots_per_hour:.1f}")
        print(f"Duration of max drawdown (hours): {(dd_end-dd_start)/slots_per_hour:.1f} (period: {timestamps[dd_start]}-{timestamps[dd_end]})")
        print(f"Wind fraction ({'optimised' if params.optimise_wind_fraction else 'default'}): {wind_frac:.2f}")
        print(f"Percentage of time in blackout: {100*blackout_slots/data_hours:.3f}")
        print(f"Battery empty (blackouts): {depletion}")
        print(f"Drawdowns of over {max_drawdown/2/slots_per_hour:.1f} storage-hours: {'; '.join(list(map(lambda d: f'{d[0]/slots_per_hour:.1f} ({timestamps[d[1]]} - {timestamps[d[2]]})', half_drawdowns)))}")
        print(f"Wind output scaled up by: {final_wind_multiple:.1f}")
        print(f"Solar output scaled up by: {final_solar_multiple:.1f}")
        if simulate_drawdowns:
            print(f"Sim - Overproduction (curtailment), percent: {100*curtailed_hours/data_hours:.1f}")
            print(f"Sim - Blackouts: {len(blackout_starts)}")
            print(f"Sim - Percentage of time in blackout: {100*sum(blackout_durations)/data_hours:.1f}")
            print(f"Sim - Blackout (start, duration) (hours): {list(zip(blackout_starts, blackout_durations))}")
        print(f"Usable datapoints (percent): {100*data.shape[1]/basedata.shape[1]:.1f}")
        print("Historical contributions by source:")
        print("           Min CF   Avg CF    Min Contr.  Avg Contr.  Max Contr.")
        contrib = data / data[TOTAL_GEN_COL]
        for i in range(FIRST_GEN_COL, len(eia_cols)):
            print(f'{eia_cols[i]:8} {cap_factors[i].min():8.3f} {np.average(cap_factors[i]):8.3f} {contrib[i].min():11.3f} {np.average(contrib[i]):11.3f} {contrib[i].max():11.3f}')
        print(f"Discarded data points: {discarded_ranges}")

    return calc_parameterised

# Minimise the maximum drawdown by adjusting the wind fraction
def optimise_wind_frac(cpfun, overbuild):
    wind_min = 0
    wind_max = 1
    while wind_min + 0.01 < wind_max:
        wind_mid = (wind_min + wind_max) / 2
        delta = (wind_max - wind_min) / 20
        _, _, _, storage_l = cpfun(wind_mid - delta, overbuild)
        l_drawdown, _, _ = get_max_drawdown(storage_l)
        _, _, _, storage_r = cpfun(wind_mid + delta, overbuild)
        r_drawdown, _, _ = get_max_drawdown(storage_r)
        if l_drawdown < r_drawdown:
            wind_max = wind_mid
        else:
            wind_min = wind_mid
    return wind_min


def get_max_drawdown(walk):
        dd_end = np.argmax(np.maximum.accumulate(walk) - walk)
        dd_start = np.argmax(walk[:dd_end]) if dd_end else dd_end
        max_drawdown = walk[dd_start] - walk[dd_end]
        return max_drawdown, dd_start, dd_end

# Get all non-overlapping drawdowns larger than n (from peak to trough).
def get_drawdowns(walk, n):
    if walk.shape[0] < 1:
        return []
    max_drawdown, dd_start, dd_end = get_max_drawdown(walk)
    if max_drawdown < n or dd_end < 1:
        return []
    ls = get_drawdowns(walk[:dd_start], n) if dd_start > 0 else []
    ls.append((max_drawdown, dd_start, dd_end))
    rs = get_drawdowns(walk[dd_end:], n) if dd_end+1 < walk.shape[0] else []
    return ls + list(map(lambda m: (m[0], m[1]+dd_end, m[2]+dd_end), rs))


def trailing_sma(vec, window):
    '''Returns a trailing rolling average of a vector, with the initial values
    the mean of all preceding values'''
    cs = np.cumsum(vec)
    cs[window:] = (cs[window:] - cs[:-window]) / window
    cs[:window] /= np.arange(1, window+1)
    return cs

def centered_sma(vec, lookahead, season_len=None):
    '''Returns a centered rolling average of a vector, with the initial and final values filled
    in with those from the following or preceding season'''
    if not season_len:
        season_len = lookahead
    icols = lookahead // 2
    fcols = lookahead - icols
    cs = np.cumsum(vec)
    cs[icols:-fcols] = (cs[lookahead:] - cs[:-lookahead]) / lookahead
    cs[:icols] = cs[season_len:season_len + icols]
    cs[-fcols:] = cs[-fcols-season_len:-season_len]
    return cs

# The EIA spreadsheet column headers.
DEMAND_COL, EXPORT_COL, TOTAL_GEN_COL, FIRST_GEN_COL, WIND_COL, SOLAR_COL, NUCLEAR_COL, HYDRO_COL = 0, 1, 2, 3, 3, 4, 5, 6
first_cols = [ 'D', 'TI', 'NG', 'NG: WND', 'NG: SUN', ]
keep_gen = [ 'NG: NUC', 'NG: WAT', ]
fossil_gen = [ 'NG: COL', 'NG: NG', 'NG: OIL', 'NG: OTH', 'NG: UNK' ]
eia_cols = first_cols + keep_gen + fossil_gen
eia_timestamp = 'UTC time'

# The corresponding gridwatch cols.  In gridwatch, some generation is unmetered,
# which shows up as a drop in demand.  Solar is estimated by Sheffield University,
# and does not show up in the BMRS demand figure (we have to add it back).
# Fossils: ocgt, ccgt, coal, biomass (wood), oil
# Renewables: wind, solar.  Apparently 30% of wind is unmetered.
# Keep: nuclear, hydro, pumped
# Interconnects: french_ict, dutch_ict, irish_ict, ew_ict (wales-irish republic),
#     nemo (Belgium), nsl (Norway).  These are imports, not exports, so must be negated.
# Also: 'other', 'north_south', 'scotland_england', 'ifa2', 'intelec_ict' appear in
# the interconnects section, so I have assumed they represent imports (I have no
# docs).
gridwatch_interconnects = [
    'french_ict', 'dutch_ict', 'irish_ict', 'ew_ict', 'nemo', 'nsl',
    'other', 'north_south', 'scotland_england', 'ifa2', 'intelec_ict',
] 
gridwatch_col_map = {
    'D': 'demand+solar',
    'TI': '-' + '-'.join(gridwatch_interconnects), # Negated: 'TI' represents exports.
    'NG': 'wind+solar+nuclear+coal+ccgt+ocgt+oil+biomass+hydro+pumped',
    'NG: WND': 'wind',
    'NG: SUN': 'solar',
    'NG: COL': 'coal',
    'NG: NG':  'ccgt+ocgt',
    'NG: OIL': 'oil',
    'NG: OTH': 'biomass',
    'NG: UNK': '',
    'NG: NUC': 'nuclear',
    'NG: WAT': 'hydro+pumped',
    }
gridwatch_cols = [ gridwatch_col_map[i] for i in eia_cols ]
gridwatch_timestamp = 'timestamp'

# A column def can be "a+b-c-d", in which case that output column
# will be the sum/difference of those input fields.
def load_csv(fname, data_col_defs, timestamp_col, delimiter='|', start_year=None):
    '''Load a CSV, returning a list of dates and an array of generation data'''
    data_cols = []
    col_map = {}
    def add_col(i, name, sign):
        if name not in col_map:
            col_map[name] = (len(data_cols), [])
            data_cols.append(name)
        col_map[name][1].append((i, sign))

    for i, col in enumerate(data_col_defs):
        for pos in col.split('+'):
            negs = pos.split('-')
            if pos and pos[0] != '-':
                add_col(i, negs[0], 1)
                negs[0] = ''
            for neg in negs:
                if neg:
                    add_col(i, neg, -1)

    with open(fname, newline='') as datfile:
        datreader = csv.reader(datfile, delimiter=delimiter, quotechar='"', quoting=csv.QUOTE_MINIMAL)
        headers = list(datreader.__next__())
        headers = [ h.strip() for h in headers ]
        indices = [ headers.index(n) for n in data_cols + [ timestamp_col ] ]
        dates = []
        rows = []
        for rec in datreader:
            nr = [ rec[i].strip() for i in indices ]
            cr = [ 0 ] * len(data_col_defs)
            for i, name in enumerate(data_cols[:-1]):
                if nr[i]:
                    for ocol, sign in col_map[name][1]:
                        cr[ocol] += float(nr[i]) * sign
            if start_year is not None:
                if int(nr[-1].split('-')[0]) < start_year:
                    continue
            # ignore rows for which the generation mix is empty (no disaggregated data before 2018).
            if not any(cr[FIRST_GEN_COL:]):
                continue
            dates.append(nr[-1])
            rows.append(cr)

    cols = list(zip(*rows)) # transpose
    return dates, np.array(cols, dtype=float)

def eia_csv_loader(start_year=None):
    def load_eia_csv(fname):
        '''Load an EIA CSV, returning (dates, data, fname)'''
        dates, data = load_csv(fname, eia_cols, eia_timestamp, delimiter='|', start_year=start_year)
        return dates, data, fname
    return load_eia_csv

def gridwatch_csv_loader(start_year=None):
    def load_gridwatch_csv(fname):
        '''Load a gridwatch CSV, returning (dates, data, fname)'''
        dates, data = load_csv(fname, gridwatch_cols, gridwatch_timestamp, delimiter=',', start_year=start_year)
        return dates, data, fname
    return load_gridwatch_csv

# Alignment only matters for 2018 EIA data (reporting from different timezones
# started at different GMT times on Jul 1 2018).
def align_csv_dates(csvs):
    '''Sequence-align the timestamps across all CSVs, then assign indices to them.
    Returns the set of csvs with each date_list replaced by a date_indices array,
    plus the mapping from indices to date strings.'''
    date_data, gen_data, filenames = zip(*csvs)
    date_graph = {}
    for dates in date_data:
        for dp, dn in zip(dates[:-1], dates[1:]):
            if dp not in date_graph:
                date_graph[dp] = set()
            if dn not in date_graph:
                date_graph[dn] = set()
            date_graph[dn].add(dp)
    ts = graphlib.TopologicalSorter(date_graph)
    date_sequence = list(ts.static_order())
    date_idx = {}
    for date in date_sequence:
        date_idx[date] = len(date_idx)
    date_id_data = []
    for dates in date_data:
        indices = np.array([date_idx[date] for date in dates], dtype=int)
        assert np.unique(indices).shape == indices.shape
        date_id_data.append(indices)
    return list(zip(date_id_data, gen_data, filenames)), date_sequence

def combine_aligned_csvs(csvs):
    '''Merges (sums) a collection of date-aligned csvs into a combined csv'''
    rows = csvs[0][1].shape[0]
    cols = 1 + max([csv[0].max() for csv in csvs])
    out = np.zeros((rows, cols), dtype=float)
    for idx, csv, _ in csvs:
        out[:, idx] += csv
    return out


def load_dir_csvs(dir, filter, loader):
    '''Load all CSVs from a directory.  Returns a list of triplets:
    (dates, data, filename), one per loaded CSV.
    '''
    csvs = []
    for i in sorted(os.listdir(dir)):
        fn = f'{dir}/{i}'
        if os.path.isfile(fn) and i.endswith('.csv') and filter(i):
            dates, data, _ = loader(fn)
            if len(dates):
                csvs.append((dates, data, i))
                print(f'{fn}: {len(dates)} records')
    return csvs

def load_all_eia_regions():
    '''Load all the EIA regional data, and construct the aggregate regions'''
    loaded = load_dir_csvs(EIA_DATA_DIR, lambda f: f.find('Region_') >= 0, eia_csv_loader(START_AT_YEAR))
    shortnames = {fn[fn.find('Region_')+7:-4]: i for i, fn in enumerate(list(zip(*loaded))[2])}
    for region, components in EIA_REGIONS.items():
        missing = [f for f in components if f not in shortnames]
        if missing:
            print(f"{region}: missing data for {missing}")
            continue
        fn = f'{region} ({"+".join(components)})'
        csvs = [loaded[shortnames[f]] for f in components]
        acsvs, dates = align_csv_dates(csvs)
        ccsv = combine_aligned_csvs(acsvs)
        loaded.append((dates, ccsv, fn))
        print(f"{fn} ({ccsv.shape[1]} records)")
    return loaded

def simulate_all_eia_regions():
    loaded = load_all_eia_regions()
    for dates, data, fname in loaded:
        print(f'''
Data: {fname}
''')
        simulate(data, SimParams(fname), 1, dates)

def simulate_eia_region(region):
    '''Load and run a specific eia region file'''
    dates, data, fname = eia_csv_loader(START_AT_YEAR)(f'{EIA_DATA_DIR}/Region_{region}.csv')
    simulate(data, SimParams(fname), 1, dates)

def simulate_all_eia_files():
    loaded = load_dir_csvs(EIA_DATA_DIR, lambda f: True, eia_csv_loader(START_AT_YEAR))
    for dates, data, fname in loaded:
        print(f'''
Data: {fname}
''')
        simulate(data, SimParams(fname), 1, dates)

# To look at how the numbers are affected by data (and startup) artifacts.
def eia_csv_by_month(file):
    '''Simulate an EIA data file multiple times, starting at different dates'''
    dates, data, fname = eia_csv_loader(None)(f'{EIA_DATA_DIR}/{file}.csv')
    for i in range(0, len(dates) - 365*24, 30*24):
        print(f"{file} (from {dates[i]})")
        simulate(data[:,i:], SimParams(f'{fname}: from {dates[i]}'), 1, dates[i:])

# There is bad data in the gridwatch csv before Feb 2018 which completely screws things (you
# can include Jan 2018 if you delete the line containing the -6e34 interchange value:
# row id: 694477, timestamp: 2018-01-08 14:10:47).  There is plenty of bad data after
# that (eg: 10-15 minute intervals where demand briefly triples), but we can cope.
def simulate_gridwatch_csv():
    '''Run the simulator over the 2018-now data'''
    fname = f'gridwatch-data/gridwatch-2018-on.csv'
    if os.path.exists(fname):
        dates, data, fname = gridwatch_csv_loader(START_AT_YEAR)(fname)
        simulate(data, SimParams(fname), 12, dates)
    else:
        print(f"No GridWatch data ({fname})")

# Figure out how much historical gridwatch data is somewhat usable.
def gridwatch_csv_by_month():
    '''Simulate the 2011-now gridwatch data multiple times, starting at different dates'''
    dates, data, fname = gridwatch_csv_loader(None)(f'gridwatch-data/gridwatch-2011-on.csv')
    for i in range(0, len(dates) - 365*24*12, 30*24*12):
        print(f"Gridwatch (from {dates[i]})")
        simulate(data[:,i:], SimParams(f'{fname}: from {dates[i]}'), 12, dates[i:])

# simulate_eia_region('US48')
# simulate_eia_region('TEX')
# simulate_eia_region('CAL')
# simulate_eia_region('NW')
# simulate_eia_region('CENT')

# simulate_all_eia_regions()
simulate_gridwatch_csv()

# To work out where the data anomalies end in a file
# gridwatch_csv_by_month()
# eia_csv_by_month('Region_TEX')
# eia_csv_by_month('Region_US48')
# eia_csv_by_month('Region_CENT')
# eia_csv_by_month('Region_MIDA')
# eia_csv_by_month('BPAT')
# eia_csv_by_month('GRID')
# eia_csv_by_month('NWMT')

# Simulate the individual BA files as well as regions.
# simulate_all_eia_files()
