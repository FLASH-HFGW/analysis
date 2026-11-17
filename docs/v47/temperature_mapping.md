# Temperature sensor mapping and data quality

| Operator sensor | Physical identity | Equipment | ODB name | Zero-based INPT index | Alias | Unit |
|---|---|---|---|---:|---|---|
|17|RF cavity — Dale1.5K, RuO₂|Temp_AVS|T4|15|T15|mK|
|18|Mixing Chamber plate — CMN143|Temp_AVS|T5|16|T16|mK|
|19|Mixing Chamber plate — CMN130|Temp_AVS|T6|17|T17|mK|

Operator numbers are not bank indices. Identity is checked through original equipment/eventID,bankINPTlength,ODBlabel,extractioncodechannelindex andschema. It is not inferred from ordering17→15 alone. Physicalnames follow operator identification; electronicsmapping is verified independently.

All three channels have260valid positive runmedians,10–11observations perSPECinterval. UnitsmK are documented by the channelmap; an empty ODBunitfield is not independent calibration. Medians use cached originalINPTobservations insidev2SPECtimestampbounds with no interpolation. OriginalschemaIDandindices remain in sensor_inventory.json.

Additional measured stage sensors include4Kplate(Mercuryindex4,Diode_4K_T K),50Kplate(index2,Pt_50K_T K),magnet(index12,RuO2_Mag_T K),still(AVS11),50mKplate(AVS12),TWPA(AVS13),noise source(AVS14)andheat switch(Mercury10). Full coverage, ranges and quality flags are retained in sensor_inventory.json. MercuryMCdiode(index8) is zero throughout and excluded.

The4Kplate diode spans3.9912–4.0569K with260valid medians. TheHEMTis documented at4Kstage; this is a stage-temperature proxy, not case/junctionthermometry. CavityPearson associations are strongest among the original3mKsensors; adding4Kplate yields stronger negative correlations. Neither is interpreted as causal. Additionalstagecorrelations are available in fullband_temperature_correlations_v2.csv and resonance/electronic correlations in results.json.
