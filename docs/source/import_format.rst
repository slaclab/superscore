Importing PVs
=============
PVs can be added in batches by importing them from a csv file.

Instructions
------------

From the "Browse PVs" page, click the "Import PVs" button and select the file you would like to import.
A pop-up will preview the parsed PVs, from which you can cancel or continue the import. If the backend 
fails to import any PV, the entire batch will fail so that the file can be adjusted and re-tried. Due 
to backend constraints, avoid importing more than 1000 PVs at a time.

Format
------

The csv file must have the header:

.. code-block::

   Setpoint,Readback,[Description,]{Tag Group 1},{Tag Group 2},...

The setpoint and readback columns can't both be empty for a given row. The description column is optional.
In the header, each column after readback / description is the name of a tag group; in each row, the data 
in each column are tags within that group. Tags can be specified as a single name, or as a comma-separated
list of names within double-quotes.

For example, the following valid csv exhibits PVs with different combinations of data:

.. code-block::

   Setpoint,Readback,Region,Area,Subsystem
   FBCK:BCI0:1:CHRGSP,FBCK:BCI0:1:CHRG,"Feedback-All","SETPOINTS","FBCK"
   ACCL:LI24:100:KLY_C_1_TCTL,,"Klystron Phases and Timing,Timing-All","LI24","Timing,Klystron Timing"
   ,BPMS:LI30:801:X,"BSA,BSA-CUHXR,BSA-CUSXR","LI30","BPMS"
