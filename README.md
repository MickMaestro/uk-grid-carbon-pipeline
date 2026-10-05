# UK grid carbon pipeline

How much CO₂ comes with a unit of electricity in Great Britain depends a lot on when you use it.
When it's windy most of the grid runs on wind and nuclear, and when it's still, gas plants fill the
gap. In January 2026 the national carbon intensity went as low as 42 g of CO₂ per kWh and as high
as 286. The longer-term picture is changing too: the January average was 279 g/kWh in 2019 and
146 g/kWh in 2026.

The National Energy System Operator (NESO) publishes these figures every half hour, nationally and
for 14 regions, through its free [Carbon Intensity API](https://carbonintensity.org.uk/). I'm
building a pipeline that collects this data every day and keeps it in a form I can query, to
answer two questions:

1. **When is electricity cleanest?** Which times of day and days of the week have the lowest
   carbon intensity, and does that change from one region to another?
2. **How quickly is the grid decarbonising?** How have carbon intensity and the fuel mix behind
   it changed since 2018, nationally and by region?

Work in progress. At the moment it downloads national carbon intensity for one day at a time and
saves the raw response locally.
