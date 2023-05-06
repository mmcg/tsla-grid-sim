# tsla-grid

This is a quick sanity check of the estimated storage requirements
for Tesla's hypothetical fossil-free energy grid,
[here](https://www.tesla.com/ns_videos/Tesla-Master-Plan-Part-3.pdf)
(description starts on p13).  It was inspired by a UK
grid simulation, [here](https://github.com/jarto/GridWatch).

The tesla proposal is complex, but a core claim is that if you overbuild
solar and wind by about 32%, keep existing nuclear and build out hydro,
then you could get by with about 90 hours of energy storage and still
maintain a reliable energy system.  They arrived at this particular
prescription by optimising the overall cost of a grid buildout for
some future fossil-free energy economy and demand profile,
under the constraint that the energy storage should reliably handle
the last 4 years of wind+solar capacity factor fluctuations
in the US (plus a 15% safety margin to handle unobserved
weather conditions).  The hourly EIA generation data is available
[here](https://www.eia.gov/electricity/gridmonitor/).

Here, we look at what amount of storage is plausible for the _current_
electricity demand profile.  For this we take Tesla's generation mix
(40:60 wind:solar), scale the total installed wind+solar to cover the
deficit left from removing historical fossil fuel electricity generation,
and simulate its performance against the observed historical wind and
solar generation variability to see whether storage is ever depleted.

Before I start (or fuel) any arguments: Tesla considered a different
energy economy - one we might build in the future - having very different
characteristics to today's.  About the only thing we have in common is
that we're both using the EIA data and we're both sizing some storage.
I wrote it to get some perspective on their work.

## Usage

Make sure you have wget and xlsx2csv installed,
then run `download-eia-data.sh` to fetch the data,
and `tsla-grid-sim.py` to do the simulation.

```sh
sudo apt install wget xlsx2csv
sh download-eia-data.sh -r
python3 tsla-grid-sim.py
```

The python code uses numpy (`python3 -m pip install numpy`).

Without `-r`, `download-eia-data.sh` will only download the
summary data file for the US lower 48 region; `-r` fetches
all of the region files as well.
Use `-a` to fetch the Balancing Authority files as well (although we can't
do much with those - the data is dirty).  The full (`-a`) EIA dataset
is about 3G; an extra 1.5G is produced when extracting the CSVs.  The regional (`-r`)
data is about one fifth of that.

## GridWatch

We can also run the simulation on 5-minute historical demand data
covering the UK, which you can download from [GridWatch](https://www.gridwatch.templar.co.uk/).
Note that the older UK data contains errors and artifacts
which will cause this code to produce nonsensical numbers.
Their download page lets you choose a date range, as well
as the columns to include (you should include all columns).

GridWatch data starting from Feb 2018 still has artifacts, but they aren't
as egregious and we can produce somewhat plausible storage estimates.
We look for that data in a file
called `gridwatch-data/gridwatch-2018-on.csv`.
Remember to start from February - there's an entry in January that
claims that one of the interconnects can transmit $6*10^{36}$ MW.

There's also a function in the code to work out how much
of the full gridwatch dataset is usable (you have to uncomment
the call to it, so I'll leave you to discover the details).
It loads `gridwatch-data/gridwatch-2011-on.csv`.

## The Lower 48

Here are a few simulations run on the EIA `Region_US48.xlsx` file,
with data to mid-April 2023 (when I downloaded it).  That file describes
the combined hourly power generation and consumption of the US lower 48
states (as well as trade with Canada and Mexico).

We'll describe the simulation [below](#Simulation), but
for now you should know that:

* `NG: WND` means "net generation - wind" (these names come from the data
  files).  The non-fossil generation types are `WND`, `SUN`, `NUC` and `WAT` (the
  last includes both hydroelectric and pumped storage).
* "Curtailment" refers to the amount of wind and solar power thrown away (this
  happens when demand is lower than supply and storage is full).
* The simulation sizes the installed renewables capacity to cover the maximum observed
  demand (including all contributions from fossil fuels), and then
  scales that up to account for the levelised capacity factors and an
  overprovisioning percentage.
* We ignore the transmission capacity constraints on intra-regional interconnects.
  * In real life these will raise total storage requirements, since they make
    it harder to transport power between sub-regions that are temporarily underproducing
    and those that are overproducing.
  * Tesla modelled the lower 48 as four regions and accounted for
    the capacity constraints between them.
  * The current capacity of the links between those regions amounts to about 1% of average demand.
  * Their cost optimiser elected to roughly triple that, to 3% of (hypothetical future) demand.
* Our calculated historical levelised capacity factors for wind and solar are somewhat
  high.  There are a few reasons:
  - The simulation estimates the (historical) installed generation capacity based on the
    highest ever previously observed power output.  But the US48 covers 4 time zones - we'll never
    see the nameplate output for the installed solar base, and it's unlikely we'd ever see
    every wind farm simultaneously producing its maximum output.  So we underestimate installed
    renewables capacity, thereby overestimating capacity factors.
  - Renewable output is locally curtailed wherever it exceeds local demand.  Since renewables
    are always locally overprovisioned (due to their variability), output is almost
    always being curtailed somewhere in the US.  This also lowers the estimated installed
    capacity.
  - For most purposes, these factors cancel out: storage is sized in units of
    "hours of expected levelised renewable power generation".
* Using aggregated regional data
  [changes the statistics](https://en.wikipedia.org/wiki/Central_limit_theorem)
  of the historical capacity factors.
  - As the output of many disparate locations are added, the data tends towards a
    [normal distribution](https://en.wikipedia.org/wiki/Normal_distribution), with
    the effect of concentrating the (observed) capacity factors towards the mean.
  - This then reduces estimated storage requirements, because renewable output
    is more predictable (steadier).
  - The amount of concentration probably depends on the size of the average
    weather system in the US (which is above my pay grade).
* We will see (historical) blackouts as drops in demand.
  - In other words, our calculated minimum battery size might not
    have prevented that same historical blackout.
  - Tesla's simulation doesn't have that problem: they are using the
    historical weather, but specifying the future demand.
* Therefore, our estimated minimum storage requirements should be
  somewhat optimistic.

With Tesla's parameters (keep existing nuclear and hydro, overbuild
renewable generation by 32%), we calculate that we need 8 hours of storage
(and we see 57% curtailment).
```
Parameters:
    Data: eia-data/Region_US48.csv
    cf_filter_duration: 504
    min_historical_cf: 0.02
    storage_hours: 90.33255993812838
    isolate_region: False
    capacity_planning_lookahead: 365.0 days
    capacity_planning_percentile: 1
    overbuild: 0.32
    calculate_dcf: True
    default_wind_dcf: 0.352
    default_solar_dcf: 0.151
    default_wind_fraction: 0.4
    keep_generators: [5, 6] - ['NG: NUC', 'NG: WAT']
Minimum storage required to avoid all blackouts (hours): 7.7
Duration of max drawdown (hours): 41.0 (period: 4722-4763)
Overproduction (curtailment), percent: 57.1
Blackouts: 0
Percentage of time in blackout: 0.0
Blackout (start, duration) (hours): []
Wind output scaled up by: 6.8
Solar output scaled up by: 40.4
Usable datapoints (percent): 100.0
Historical contributions by source:
           Min CF   Avg CF    Min Contr.  Avg Contr.  Max Contr.
NG: WND     0.056    0.488       0.006       0.094       0.246
NG: SUN     0.000    0.225       0.000       0.021       0.127
NG: NUC     0.505    0.855       0.089       0.203       0.295
NG: WAT     0.055    0.532       0.007       0.069       0.126
NG: COL     0.237    0.570       0.096       0.218       0.353
NG: NG      0.236    0.505       0.142       0.366       0.497
NG: OIL     0.003    0.092       0.000       0.002       0.041
NG: OTH     0.153    0.271       0.011       0.019       0.069
NG: UNK     0.000    0.000       0.000       0.000       0.000
Discarded data points: []
```

If we also replace nuclear and hydro with renewables, our storage
needs rise to 13 hours - because (variable output) wind and solar
have stepped in to cover for (relatively fixed output) nuclear and
dispatch-on-demand hydro (which is, for our purposes, a huge self-recharging
battery).  Here are the differences between this run and the prior one:
```
Parameters:
    keep_generators: [] - []
Minimum storage required to avoid all blackouts (hours): 12.7
Duration of max drawdown (hours): 88.0 (period: 4698-4786)
Overproduction (curtailment), percent: 51.9
```

Thus far, Tesla's storage number is looking plausible - our (admittedly
optimistic) storage estimates are considerably lower than theirs.  There are, of
course, many differences between their scenario and ours.  One such
difference is that in Tesla's paper, that 32% number (that we have treated
as how much we should overbuild renewables above peak demand) actually referred
to the amount of power that was _curtailed_ - power that had to be thrown away
because storage was full.  Because they have at most a few days of storage, this
implies that their generators must have been sized at about 32% above average
annual demand (not peak, and not even peak seasonal).

If we tried to do the same thing today, we'd need at least 20 days of
storage:

```
Parameters:
    capacity_planning_percentile: 0
    overbuild: 0.32
    keep_generators: [5, 6] - ['NG: NUC', 'NG: WAT']
Minimum storage required to avoid all blackouts (hours): 469.0
Duration of max drawdown (hours): 1934.0 (period: 19-1953)
Overproduction (curtailment), percent: 26.6
Blackouts: 63
Percentage of time in blackout: 1.8
Blackout (start, duration) (hours): [(395, 4), (419, 16), ..., (1930, 11), (1954, 2)]
```

Tesla's numbers might make sense if their hypothetical future
energy demand is much less seasonal
than the current one.  Which seems to be the case: in their paper, lots of new load
is added (they roughly tripled electricity generation), and the majority of it is
nonseasonal or has its own storage and can be deferred until there is excess
supply (eg: hydrogen production, fuel production, industrial heat production).
Relative to all of this new baseload, the seasonal parts for which they had data diminish
in importance - expanded heat pump usage (which triples from today), car
charging (and hence driving) seasonality, etc.  All of this newly created
demand is stacked on top of today's demand profile - so today's contribution
to seasonality drops by about two thirds.  Also, since they get to design
how all of this new industry fits together with known wind and solar generation
profiles, they can take advantage of every optimisation opportunity, and
balance the mix of storage types to use up any gaps - optimality which doesn't
tend to arise naturally unless there is an economic incentive to do so.  The
result is that far less power is discarded overall because there is an optimal
amount of external storage to fill, and also less overbuilding to do because
the remaining supply deficits are smaller.  They also get to build out
hydroelectric as they see fit (we use the historical figures).

Interestingly, Tesla's mix specifies only 4.9 hours of battery; the vast majority
of the 90 hours was stored as hydrogen.  Given the observations above (8h
for today's economy and reduced seasonality in their energy demand mix),
it seems likely that their battery storage is sized to precisely
cover their grid storage needs - i.e. that all of that hydrogen energy storage
is intended to support industrial and chemical processes.  They
also quoted an RTE for hydrogen storage of 95% - an efficiency
much too high for (eg) a round trip through an electrolyser and a fuel
cell, but pretty reasonable if you're only considering
gas compression overhead and heat loss.

If we overbuild by 0% (sizing renewables to the exact maximum demand)
we need about 68 hours (3 days) of battery if you keep nuclear and hydro,
or 82 hours without them.

## Reliability

People occasionally claim that for renewables to work you'd need at least
three months of storage.  Typically, their misconception is that wind and
solar power generation will be sized to match average annual demand (rather
than peak demand) - implying that you must save up energy in spring
for use during the summer.

Let's see what happens when we try that.

```
Parameters:
    Data: eia-data/Region_US48.csv
    capacity_planning_percentile: 0
    overbuild: 0
    keep_generators: [5, 6] - ['NG: NUC', 'NG: WAT']
Minimum storage required to avoid all blackouts (hours): 2732.8
Duration of max drawdown (hours): 15177.0 (period: 0-15177)
Overproduction (curtailment), percent: 9.8
Blackouts: 443
Percentage of time in blackout: 15.4
Blackout (start, duration) (hours): [(515, 300), (804, 284), ..., (39730, 3), (40283, 2)]
```

So if you start with a 4 day battery, you are blacked out for 56 days
per year.  Installing about 3.8 months of storage would have prevented any
blackouts during the (historical) study period - roughly matching intuition.

Obviously, sizing your renewables to match the average demand isn't sensible:
on average you are depleting your battery at least as fast as you are charging it.
Instead, if you are planning an installation, you would start by sizing your
generation capacity somewhere near peak demand - the same as
you would for a fossil fuel mix.  From there you have a reliability
tradeoff to make: if you want to target, say, less than 5 hours of
blackouts per year, you can scale up your generation capacity (so that a
smaller battery can be charged faster) or scale up your battery (so that it
lasts longer once charged), or both.  You choose the cheapest combination
that hits some reliability target, and then scale that up to highest
reliability you can afford.  100% reliability is mathematically impossible.

Exactly the same calculus applies to the current grid.  Consider a storm
that takes out a bunch of power lines (or - totally hypothetically - knocks
out the fuel supply to all of your 
[gas fired plants](https://en.wikipedia.org/wiki/2021_Texas_power_crisis)).
If a storm like that happens once every three years and you are required by
law to average 5 hours/year or less of downtime, then the "overcapacity"
investment you must make is in keeping enough maintenance crews on hand
to restore average storm damage within an average of 15 hours.
So power failures are something everyone already copes with (perhaps by
purchasing a generator, or perhaps by candlelit dinners) - and balancing
system reliability against costs is routinely done today.
"Reliable baseload power" is no more reliable than its delivery system.

Which brings us back to our simulation.
It calculates the amount of battery storage that would prevent
any blackouts given the observed historical weather. This battery size does
not (and cannot) guarantee 100% reliability for _future_ weather.  Future
weather could be wildly different to anything in that data set.  The storm
that knocked out Texas happened to fall into our five year study period -
but they only see storms like that once every ten or twenty years, so we
could just as easily have missed it.  We've never seen a nuclear winter.

So what _can_ we say about reliability of our minimum storage estimates?

As a thought experiment, imagine that there are various combinations of
weather conditions that (you calculate) would drain your system and
eventually cause a blackout.  You have a meteorological model that can
calculate how often, on average, any particular combination of weather
conditions should occur and how long those conditions would typically persist.
If you're mathematically inclined
you might be able to invert the weather statistics embedded in this model
to directly calculate your system's reliability (eg: probabilities of
seeing outages of various durations within any given timeframe).  Otherwise,
you could use that weather model to simulate thousands of years of random (but
realistic) weather conditions, and numerically estimate your system's
reliability.  You could tweak your design until you hit your desired numbers.

Our historical dataset is one such "realistic simulation", and covers about 5 years.
If a simulation covers 5 years, you would expect to encounter about 50% of the
weather events that occur once every 5 years (where an "event" might be, eg,
an unusually widespread lull in windspeed that last for a certain time).
So in the following 5 year period, you'd expect that 25% of the 5-year
events that you encounter would be ones you haven't seen in your simulation.
Of that 25%, there is a 50% chance that at least one of them has more
severe effects on your system than any that you simulated.  So if you
installed the minimum sized battery, you have at least a 12.5%
chance of some sort of power outage somewhere in that 5 year period.

That 12.5% includes just the failures expected to occur from 5 year weather
events - we must actually integrate over the contributions of all of the
other timescales to get a true estimate.  In any case, we don't end up
with a very reliable system (it isn't easy to demonstrate on the US48,
but we'll return to this when we look at the regional data).  I imagine
that Tesla's carefully optimised 4.9 hours of battery storage might need
similar adjustments.

The good news is that it's easy to build in a sizeable margin of safety:
in the case of the lower 48, a relatively small (32%) overbuild in
generation capacity resulted in an 8x drop in storage requirements (6x
if you're also eliminating nuclear and hydro), or,
[equivalently](https://en.wikipedia.org/wiki/Random_walk),
a roughly 64x increase in the expected time between blackouts.
Even better: reasonably realistic weather statistics gathered
from long term data (or from weather models) are readily available.
There are still tail events that can't be captured (or their probability
estimated), but for those you create contingency plans.

By the way, I calculated (from Tesla's model results on page 20)
that renewables curtailment comes out to about 28% - so perhaps
their "15% margin of safety" came from bumping that up to 32%.
In our terms, that's an overbuild of a few additional percent
over the bare minimum system analysed above.

## Simulation

The EIA data contains hourly samples of electrical demand within
a region, trade (electricity exports or imports), and the
amount of electricity generated within the region by each
type of fuel used.

The simulation tries to account for historical changes in supply
and demand (but not changes in technology - eg expected capacity
factor from a new onshore wind farm - which improved markedly
in 2021).  So the estimates of historical installed capacity -
as well as the estimate of how much installed capacity we need
to cover demand - are all per-hour.

From the data, we:
* Estimate the historical installed capacity for each renewable.
  - For each hour we set this to the maximum value we have seen in any
    prior hour (or the current one).  This lets us adapt to
    grid expansion (but not decommissioning).
  - To smooth variations in the early estimates (caused by
    the data starting in a particular season), we can also
    look ahead for a near-future maximum value.  By default
    this is one year.
* Use that to calculate the historical (observed) capacity
  factors for wind and solar for each hour, as well as their
  simple averages (i.e. the levelised capacity factors over
  the entire period).
* Calculate how much demand must now be covered by renewables
  once fossil (and optionally hydroelectric, nuclear, and
  trade) have been eliminated.
* Calculate the (new) required renewable capacity for each hour:
  - We start with a weighted average of:
    - The maximum renewables demand ever seen prior to that hour (optionally with lookahead).
    - The rolling average demand from 6 months prior to 6 months after that hour.
    - This lets us size capacity based on peak or levelised demand.
  - We then size that up by the overbuilding percentage.
  - We split that electricity demand between wind and solar
    (40% wind by default), and scale each up to an installed
    (nameplate) capacity using the levelised capacity factors
    derived earlier.

Once we have sized our installed renewables, we run it
against the (calculated) per-hour historical capacity
factors and demand figures, and track charge and discharge
cycles of the specified-size battery.  The battery starts
off full, and isn't allowed to fall below empty; an empty
battery is assumed to represent a power outage.  The maximum
drawdown (assuming an infinite battery) is also calculated, and
is reported as the "minimum storage size required to avoid
blackouts" headline figure.

Some of the regional data files have artifacts - for example,
`Region_CENT` (Central) has some initial solar data, then
several months where that data wasn't reported (perhaps their
only solar farm went offline?) - which means the simulation
will assume that the capacity factors were zero for
months.  Lots of the eastern and
southeastern regions have very little solar installed (`MIDW`
solar has an average solar capacity factor of 16% but
contributed less than 0.3% of generated power).  We can't
simulate replacing everything with wind+solar without
historical capacity factor data,
so we try to filter out bad data.  We discard data points
for which renewables capacity factors averaged over the three
weeks surrounding that hour are less than 2% of the maximum
(previously observed) nameplate capacity.  If that filtering
leaves a file with less than a year and a half of viable data
points, we skip the file.  In the end, this filtering drops
five files, but doesn't drop many ranges within the
remaining files.  Note that some aggregated regions (such
as `Eastern`) are the sum of many (mainly dropped) subregions,
but are themselves processed - so our estimates are suspect
on these aggregated regions as well.

The UK gridwatch data is unusable before July 2017 (bad
values in the solar data); there are also some egregious
error in the interchange data (the last of which is in
row `id: 694477, timestamp: 2018-01-08 14:10:47`).
Downloads should start from Feb 2018 (there are
many artifacts after that, but they are not fatal).
The date-range dropping also removes the center of
a particularly long period of low renewables generation
near Christmas 2021 (data cleaning is an imperfect science)


## Regional Storage Requirements

We noted some problems with using the US48 data:

* The lower 48 is huge (3M square miles): most weather systems are smaller than it,
  and it is heavily developed everywhere.  This causes averaging effects which
  make our estimates optimistic.
* In real life there are transmission capacity constraints between regions.
  These are quite restrictive - the major interconnects can collectively handle
  something like 1% of total demand.
* We also have UK data (GridWatch).  The UK has limited-capacity interconnects
  with its near neighbors, and on its own, it has a surface area of a little
  over a third of that of Texas (which is about 8.5% of the lower 48).  Many
  weather systems are bigger than it (and can encompas its neighbors as well),
  and long periods of low wind are not uncommon.  The historical solar capacity
  factor is only 0.13 - making the UK a difficult problem.

So it makes sense to run the simulation on smaller regions - which,
individually, should have larger storage requirements.  Since there
are also interconnects into these regions which can be used to defray
shortages, we will probably somewhat overestimate the storage required.

Maps of the US grid regions and subregions are
[here](https://www.epa.gov/green-power-markets/us-grid-regions).
In terms of our region data files:
* WECC: NW, CAL, SW
* MRO: CENT and a few states from MIDW
* Texas RE: TEX
* SERC: TEN, SE, FLA, CAR, a few states from MIDA and MIDW
* RF: most of MIDA
* NPCC: NY, NE

Tesla modeled interconnects between four regions:
* Western: NW, CAL, SW
* Central: CENT, MIDW
* Texas: TEX
* Eastern: NE, NY, MIDA, TEN, SE, FLA, CAR

The US48 is administered as 3 regions:
* Western
* Texas
* Central and Eastern

Here are the headline numbers (hours of storage) for 40:60 wind:solar
and a 32% overbuild.  To revisit the "reliability" issue discussed
earlier, we'll do this for several different starting points in the data:

| Data: | 2018-2023 | 2019- | 2020- | 2021- |
|-|-|-|-|-|
| Region_CAL.csv | 10.3 | 10.3 | 4.7 | 5.0 |
| Region_CENT.csv | 124.3 | 24.2 | 24.2 | 24.2 |
| Region_MIDA.csv | 219.9 | 53.3 | 62.6 | 14.5 |
| Region_MIDW.csv | 30.8 | 30.4 | 27.1 | 37.4 |
| Region_NE.csv | 11.4 | 11.4 | 11.4 | 11.4 |
| Region_NW.csv | 27.9 | 28.3 | 10.6 | 12.0 |
| Region_SW.csv | 19.7 | 20.3 | 7.2 | 6.4 |
| Region_TEX.csv | 36.0 | 36.2 | 38.4 | 43.6 |
| Region_US48.csv | 7.7 | 9.9 | 4.5 | 4.6 |
| Western (NW+CAL+SW) | 9.7 | 9.8 | 4.3 | 4.3 |
| Central (CENT+MIDW) | 35.1 | 36.7 | 31.6 | 37.6 |
| Texas (TEX) | 36.0 | 36.2 | 38.4 | 43.6 |
| Eastern (NE+NY+MIDA+TEN+SE+FLA+CAR) | 356.0 | 9.3 | 8.1 | 6.4 |
| Lower48 (US48) | 7.7 | 9.9 | 4.5 | 4.6 |
| CentralAndEastern (CENT+MIDW+NE+NY+MIDA+TEN+SE+FLA+CAR) | 270.6 | 8.9 | 7.9 | 12.6 |
| All (CENT+MIDW+NE+NY+MIDA+TEN+SE+FLA+CAR+TEX+NW+CAL+SW) | 7.7 | 9.9 | 4.5 | 4.6 |
| gridwatch-data/gridwatch-2018-on.csv | 26.2 | 26.6 | 18.4 | 17.0 |

I suspect there is some bad data in 2018 for certain Eastern regions - disaggregated
reporting only started in July 2018, and a number of the Balancing Authorities
seem to have taken some time to sort out their IT issues.  To be fair,
[2018](https://www.climate.gov/news-features/blogs/beyond-data/2018s-billion-dollar-disasters-context)
and
[2019](https://en.wikipedia.org/wiki/2018%E2%80%9319_North_American_winter)
had some pretty wild weather as well - it's not clear how much
2018 should be discounted.

Note that `CENT` and `MIDA` (and gridwatch) were the only regions that
had ranges discarded for lack of data; not coincidentally they
have outlier estimated storage requirements.  Here are the date
ranges that were dropped (as well as their durations - in hours
for the US files and in 5 minute increments for GridWatch):

```
$ python3 tsla-grid-sim.py | grep -E ' Data:|points: \[\('
    Data: Region_CENT.csv
Discarded data points: [(1218, '2018-07-01 06:00:00', '2018-08-21 00:00:00')]
    Data: Region_MIDA.csv
Discarded data points: [(251, '2018-07-01 05:00:00', '2018-07-11 16:00:00'), (1260, '2018-07-19 18:00:00', '2018-09-10 06:00:00'), (286, '2020-01-12 04:00:00', '2020-01-24 02:00:00')]
    Data: gridwatch-data/gridwatch-2018-on.csv
Discarded data points: [(3162, '2021-12-15 03:15:37', '2021-12-26 02:45:37')]
```

Our filtering strategy discarded 11 days of UK data near
Christmas 2021 - because the average capacity factors for
wind and solar were both under 2% for that period and for
10 days before and after.  This probably isn't bad data -
Christmas seems to be problematic for UK renewables.
Disabling the filtering raises the UK storage estimate
by 5 hours (to 30.9).

We also gave up on 5 files - all in the US Eastern region (these
had less than a year and a half of data left after filtering
unusable rows).  Notice that `Eastern` and `CentralAndEastern`
also had outlier estimates for 2018:

```
$ python3 tsla-grid-sim.py | grep -E 'insufficient'
Region_CAR.csv: insufficient renewables datapoints
Region_FLA.csv: insufficient renewables datapoints
Region_NY.csv: insufficient renewables datapoints
Region_SE.csv: insufficient renewables datapoints
Region_TEN.csv: insufficient renewables datapoints
```



## An Optimiser?

The numbers so far seem pretty useful
for understanding the storage problem.
But the "one size fits all" 40:60 wind:solar mix causes
inefficiencies for [many regions](https://www.eia.gov/todayinenergy/detail.php?id=39832).
Here are some runs on the 2019-2023 data giving hours of storage
assuming various wind:solar fractions (still with an overbuild of 32%):

| Wind fraction: | 0.0 | 0.2 | 0.4 | 0.6 | 0.8 | 1.0 |
|-|-|-|-|-|-|-|
| Region_CAL.csv | 12.0 | 10.6 | 10.3 | 11.2 | 19.4| 69.8 |
| Region_CENT.csv | 33.8 | 27.0 | 24.2 | 21.7 | 30.8 | 43.2 |
| Region_MIDA.csv | 117.4 | 80.0 | 53.3 | 35.7 | 27.1 | 29.4 |
| Region_MIDW.csv | 196.4 | 39.5 | 30.4 | 28.6 | 33.7 | 85.3 |
| Region_NE.csv | 33.4 | 15.1 | 11.4 | 10.3 | 13.0 | 35.8 |
| Region_NW.csv | 127.2 | 35.7 | 28.3 | 24.4 | 20.9 | 41.3 |
| Region_SW.csv | 23.1 | 19.0 | 20.3 | 33.2 | 72.2 | 119.8 |
| Region_TEX.csv | 48.4 | 41.9 | 36.2 | 30.9 | 26.6 | 38.5 |
| Region_US48.csv | 27.0 | 15.2 | 9.9 | 7.3 | 5.5 | 16.1 |
| Western (NW+CAL+SW) | 31.6 | 16.8 | 9.8 | 5.3 | 5.5 | 27.1 |
| Central (CENT+MIDW) | 67.1 | 38.6 | 36.7 | 34.8 | 33.0 | 35.7 |
| Texas (TEX) | 48.4 | 41.9 | 36.2 | 30.9 | 26.6 | 38.5 |
| Eastern (NE+NY+MIDA+TEN+SE+FLA+CAR) | 33.6 | 13.0 | 9.3 | 14.7 | 30.6 | 72.8 |
| Lower48 (US48) | 27.0 | 15.2 | 9.9 | 7.3 | 5.5 | 16.1 |
| CentralAndEastern (CENT+MIDW+NE+NY+MIDA+TEN+SE+FLA+CAR) | 74.2 | 17.8 | 8.9 | 8.1 | 12.3 | 29.1 |
| All (CENT+MIDW+NE+NY+MIDA+TEN+SE+FLA+CAR+TEX+NW+CAL+SW) | 27.0 | 15.2 | 9.9 | 7.3 | 5.5 | 16.1 |
| gridwatch-data/gridwatch-2018-on.csv | 100.6 | 32.7 | 26.6 | 21.3 | 22.8 | 43.6 |

So the US48 seems to do best overall with 80% wind, and
the big four regions seem to want 60-80% wind
with the exception of Eastern, which does better
with 60% solar.  Note that the capacity factor
for solar in Eastern is only around 8% (compared
to 35% for wind), so 60% (levelised) solar would
represent a large overbuild in nameplate solar
capacity - it is unlikely to be the most cost-effective
build for the region (I assume because it is usually
[overcast](https://www.currentresults.com/Weather-Extremes/US/cloudiest-cities.php)
near the great lakes).  We don't
seem to have good solar data for the eastern region
anyway, and there is almost none for Central (the
data we have indicates that solar contributes
about 0.25% of the generation mix there, though
there may be some underreporting).

Similarly, the 32% overbuild was Tesla's number, for
their own energy economy (and we use it wrongly anyway).
There is no reason to think it is the optimal
figure for today's energy mix (though it seems to produce
somewhat reasonable results).  We briefly looked at this
for the lower 48, so I won't include a table here.

To come up with more realistic numbers, we'd need an optimiser
that chooses the final installed wind:solar mix, the
overbuild percentage and the battery size, minimising
costs.  The inputs are the price per installed MW of
solar and wind (and per MWh, if you care about depreciation)
and the price per MWh of storage; you
might also target a blackout percentage (presumably
defaulting to 0% - although we already discussed the
reliability of storage size estimates derived from
historical data).

But our data probably isn't good enough to draw any
firm conclusions from such an exercise, and I already
got what I came for.

## End Notes

A few thoughts on Tesla's proposal:

* Tesla's cost estimates are for a finely tuned, highly balanced
  system:
  - This seems unlikely to arise naturally in an unplanned
    economy (eg: the west).  We might make some progress with
    economic incentives, but competitive capitalism seems
    inconsistent with global optimisation.
  - Authoritarian nations might have a better shot at it,
    but they'd be hard pressed to get there without buy-in
    from everyone else.  The continued global haggling over
    carbon emission targets is an instructive example.
  - If we can't approach the efficiency of their model,
    the implementation cost probably blows out past that
    of fossil fuel capex (not that that's a fatal flaw).
* The study optimises costs for the US, then scales that cost 6x to
  approximate the world.  However, the US would appear to be a uniquely
  inexpensive region - it is huge and highly developed and almost always
  has wind and solar somewhere.  Conversely, it is not uncommon for
  the UK and its near neighbors to be becalmed for weeks at a time.
  - You need strategically planned large capacity long
    distance interconnects to begin to tackle that problem.
  - The roaring forties, furious fifties and screaming
    sixties might be fairly reliable (solar power is dumped into
    that system every day)
    - But that is a long way away from Europe.
    - And would (presumably) involve wind farms floating in deep water and
      extremely long superconducting undersea cables.
    - Although the southern tip of Chile and Argentina is right in that
      zone - perhaps they will end up exporting power to the north.
  - Absent something like that, you'd need a careful analysis
    of global weather patterns and correlations, a lot
    of money, and a lot of luck.
  - A world suddenly conscious about energy security
    might be a little wary of that kind of distributed global
    infrastructure.
* People seem to assume that a modern society requires five nines supply reliability
  for peak load energy consumption.  What if that assumption is wrong?
  - Perhaps the _consumption_ of energy should be more flexible, and
    its management more dynamic.
  - Handling fluctuating energy supply would require coordination
    between industry, authorities, and policy makers.
    - See, eg, China and Europe managing their recent energy crises.
  - We're talking about a global sea change in energy -
    the foundation of modern society.
  - What else should change to accommodate it?

## License

At your option, you may treat this file and the
accompanying code as either released to the public domain
or released under a BSD 2-clause license.

Please do not cite this work in support of any partisan talking
points (for or against renewables, nuclear, CCS, ...).
I wrote the code because all the competing camps and lobby
groups spout so much bullshit that it has become impossible to
know who's lying about what.  It is then amplified by idiots.
If you're quoting these numbers, you are probably one of them.

