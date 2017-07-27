##summary_layer=vector
##aggregate_field=field summary_layer
##test=multiple field summary_layer
##stat_field=field summary_layer
##output_layer=output vector


from qgis.core import *
from PyQt4.QtCore import *

inlayer = processing.getObject(summary_layer)
dissolve_field_index = inlayer.fieldNameIndex(aggregate_field)
stat_field_index = inlayer.fieldNameIndex(stat_field)

#Find unique values present in the dissolve field
unique_values = set([f[aggregate_field] for f in processing.features(inlayer)])
print unique_values

sum_unique_values = {}
attributes = [f.attributes() for f in processing .features(inlayer)]

for unique_value in unique_values:
    val_list =[f_attr[stat_field_index] for f_attr in attributes if f_attr[dissolve_field_index] == unique_value]
    sum_unique_values[unique_value] = sum(val_list)

#run the regular Dissolve algorithm
processing.runalg("qgis:dissolve", inlayer, "false", aggregate_field, output_layer)

#add a new attribute called 'SUM' in the output layer
outlayer = processing.getObject(output_layer)
provider = outlayer.dataProvider()
provider.addAttributes([QgsField('SUM', QVariant.Double)])
outlayer.updateFields()

#set the value of the 'SUM' field for each feature
outlayer.startEditing()
new_field_index = outlayer.fieldNameIndex('SUM')
for f in processing.features(outlayer):
    outlayer.changeAttributeValue(f.id(), new_field_index, sum_unique_values[f[aggregate_field]])
outlayer.commitChanges()

#Delete all fields except the aggregate- and stat-field
outlayer.startEditing()
fields_to_delete = [fid for fid in range (len(provider.fields())) if fid != new_field_index and fid != dissolve_field_index]
provider.deleteAttributes(fields_to_delete)
outlayer.updateFields()
outlayer.commitChanges()
