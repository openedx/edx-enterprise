#!/bin/bash
CUSTOMER=$(./manage.py lms manufacture_data --model enterprise.models.enterprise_customer)
CONFIG=$(./manage.py lms manufacture_data --model integrated_channels.canvas.models.CanvasEnterpriseCustomerConfiguration --enterprise_customer $CUSTOMER)
AUDIT=$(./manage.py lms manufacture_data --model integrated_channels.integrated_channel.models.ContentMetadataItemTransmission --integrated_channel_code CANVAS --content_title TEST --plugin_configuration_id $CONFIG --enterprise_customer $CUSTOMER)

printf "New customer: $CUSTOMER \n"
printf "Canvas config: $CONFIG \n"
printf "Audit: $AUDIT \n"
