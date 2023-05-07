# tsla-grid

This uses EIA historical power generation data to simulate
the grid-scale storage required to avoid power outages on
a renewables-powered grid.

Description in [tsla-grid.md](./tsla-grid.md).

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

## License

See [tsla-grid.md](./tsla-grid.md#License).
