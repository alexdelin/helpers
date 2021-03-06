import csv
import re
import json
import uuid
import copy
from datetime import datetime
from io import StringIO

from dateutil import parser

from shorthand.utils.rec_lib import get_hex_int


UUID_PATTERN = r'^[0-9A-F]{8}-[0-9A-F]{4}-4[0-9A-F]{3}-'\
               r'[89AB][0-9A-F]{3}-[0-9A-F]{12}$'

ALL_TYPES = [
    "int", "line", "date", "bool", "real", "uuid",
    "range", "enum", "size", "regexp"]


class RecordSet(object):
    """Record Set object which holds the field configuration
    and full record contents for one type of records in a GNU
    recfile
    """

    def __init__(self, config):
        super(RecordSet, self).__init__()
        if config:
            if self.validate_config(config):
                self.config = config
            else:
                raise ValueError('Got Invalid configuration')
        else:
            self.config = {}
        self.fields = {}
        self.records = {}

    def validate_config(self, config):
        '''Validate configuration for a record set
        '''

        # check that all custom types referenced actually exist
        for custom_type in config.get('custom_types', {}).keys():
            link_depth = 1
            next_type = config.get('custom_types').get(custom_type)
            while True:
                if link_depth > 10:
                    raise ValueError(f'Exceeded custom type link threshold '
                                     f'of 10 for custom type {custom_type}')
                if not next_type:
                    raise ValueError(f'custom type {custom_type} '
                                     f'is not defined')
                elif next_type.get('type') == 'custom':
                    next_type = config.get('custom_types').get(
                        next_type['name'])
                    link_depth += 1
                    continue
                elif next_type.get('type') in ALL_TYPES:
                    # We found a valid type definition
                    break

        # check that prohibited and/or non-allowed fields are not referenced
        has_prohibited_fields = False
        if config.get('prohibit'):
            prohibited_fields = config.get('prohibit')
            has_prohibited_fields = True
        else:
            prohibited_fields = []

        has_allowed_fields = False
        if config.get('allowed'):
            allowed_fields = config.get('allowed')
            has_allowed_fields = True
        else:
            allowed_fields = []

        if config.get('mandatory'):
            for mandatory_field in config.get('mandatory', []):
                if has_prohibited_fields and \
                        mandatory_field in prohibited_fields:
                    raise ValueError(f'Prohibited field {mandatory_field} '
                                     f'specified as mandatory')
                if has_allowed_fields and \
                        mandatory_field not in allowed_fields:
                    raise ValueError(f'Non-allowed field {mandatory_field} '
                                     f'specified as mandatory')

        if config.get('unique'):
            for unique_field in config.get('unique', []):
                if has_prohibited_fields and unique_field in prohibited_fields:
                    raise ValueError(f'Prohibited field {unique_field} '
                                     f'specified as unique')
                if has_allowed_fields and unique_field not in allowed_fields:
                    raise ValueError(f'Non-allowed field {unique_field} '
                                     f'specified as unique')

        if config.get('key'):
            key_field = config.get('key', [])
            if has_prohibited_fields and key_field in prohibited_fields:
                raise ValueError(f'Prohibited field {key_field} '
                                 f'specified as prmary key')
            if has_allowed_fields and key_field not in allowed_fields:
                raise ValueError(f'Non-allowed field {key_field} '
                                 f'specified as primary key')
            if key_field in config.get('auto', []):
                raise ValueError(f'Primary key field "{key_field}" '
                                 f'cannot be auto-generated')

        if config.get('field_types', {}).keys():
            for typed_field in config.get('field_types', {}).keys():
                if has_prohibited_fields and typed_field in prohibited_fields:
                    raise ValueError(f'Prohibited field {typed_field} '
                                     f'has a type defined')
                if has_allowed_fields and typed_field not in allowed_fields:
                    raise ValueError(f'Non-allowed field {typed_field} '
                                     f'has a type defined')

        if config.get('sort'):
            for sort_field in config.get('sort', []):
                if has_prohibited_fields and sort_field in prohibited_fields:
                    raise ValueError(f'Prohibited field {sort_field} '
                                     f'specified as sort')
                if has_allowed_fields and sort_field not in allowed_fields:
                    raise ValueError(f'Non-allowed field {sort_field} '
                                     f'specified as sort')

        # check that regexp types are valid
        regexp_types = [type_def
                        for type_def in config.get('custom_types', {}).values()
                        if type_def['type'] == 'regexp']
        regexp_types.extend([type_def
                             for type_def in config.get('field_types',
                                                        {}).values()
                             if type_def['type'] == 'regexp'])
        for regexp_type in regexp_types:
            re_pattern = regexp_type.get('pattern')
            is_valid = True
            if not re_pattern:
                is_valid = False
            try:
                re.compile(re_pattern)
            except re.error:
                is_valid = False
            if not is_valid:
                raise ValueError(f'Regex pattern '
                                 f'"{regexp_type.get("pattern")}"'
                                 f' is invalid')

        # check that range types are valid
        range_types = [type_def
                       for type_def in config.get('custom_types', {}).values()
                       if type_def['type'] == 'range']
        range_types.extend([type_def
                            for type_def in config.get('field_types',
                                                       {}).values()
                            if type_def['type'] == 'range'])
        for range_type in range_types:

            max_value = range_type.get('max')
            min_value = range_type.get('min')
            if isinstance(min_value, int) and isinstance(max_value, int):
                if min_value >= max_value:
                    raise ValueError(f"Invalid range with maximum value "
                                     f"{max_value} and minimum value "
                                     f"{min_value}")
            elif not isinstance(min_value, (int, type(None))) and \
                    not isinstance(max_value, (int, type(None))):
                raise ValueError(f'Invalid range type {range_type}. Max '
                                 f'and min must be either integers or None')

        # check that size types are valid
        size_types = [type_def
                      for type_def in config.get('custom_types', {}).values()
                      if type_def['type'] == 'size']
        size_types.extend([type_def
                           for type_def in config.get('field_types',
                                                      {}).values()
                           if type_def['type'] == 'size'])
        for size_type in size_types:
            if not size_type.get('limit') > 0:
                raise ValueError('Size types must have a limit '
                                 'greater than zero')

        # check that enum types are valid
        enum_types = [type_def
                      for type_def in config.get('custom_types', {}).values()
                      if type_def['type'] == 'enum']
        enum_types.extend([type_def
                           for type_def in config.get('field_types',
                                                      {}).values()
                           if type_def['type'] == 'enum'])
        for enum_type in enum_types:
            if not enum_type.get('values'):
                raise ValueError('Enum types must specify all allowed values')

        # check that size constraints for the record set are valid
        if config.get('size'):

            if config.get('size', {})['amount'] <= 0:
                raise ValueError('Size limit for a record set must '
                                 'be greater than zero')

        # check all auto-generated fields have a supported type
        for auto_field in config.get('auto', []):

            auto_field_type = config.get('field_types', {}).get(auto_field, {})
            if auto_field_type.get('type') == 'custom':
                auto_field_type = config.get('custom_types', {}).get(
                    auto_field_type['name'])

            if auto_field_type.get('type') not in ['date', 'int', 'uuid']:
                raise ValueError(f'Cannot auto-generate a value for '
                                 f'field {auto_field} of type '
                                 f'{auto_field_type.get("type")}')

        # If we have not found any issues
        return True

    def validate_record(self, record: dict):
        '''Validate an individual record against its defined
        type and properties. Modifies the contents of the record
        if needed.

        Returns a tuple of (error_message, processed_record)
        '''

        processed_record = copy.deepcopy(record)

        # Validate Primary Key
        primary_key_field = self.config.get('key')
        if primary_key_field:
            if not processed_record.get(primary_key_field):
                return f'Missing primary key field {primary_key_field}', None
            if len(processed_record.get(primary_key_field)) > 1:
                error_message = f'Primary key field {primary_key_field} '\
                                f'can only have a single value per record'
                return error_message, None

        # Validate types of all specified fields
        for field_name, field_values in record.items():
            field_type = self.config.get('field_types', {}).get(field_name, {})

            # Get the full type definition if it is a custom type
            if field_type.get('type') == 'custom':
                field_type = self.config.get('custom_types', {}).get(
                    field_type['name'])

            # Validate int field
            if field_type.get('type') == 'int':
                processed_record[field_name] = []
                for field_value in field_values:
                    try:
                        if field_value[:2] == '0x' or field_value[:3] == '-0x':
                            num_value = get_hex_int(field_value)
                        else:
                            num_value = int(field_value)
                        processed_record[field_name].append(num_value)
                    except ValueError:
                        error_message = f"can't convert value "\
                                        f"\"{field_value}\" of field "\
                                        f"\"{field_name}\" to an int"
                        return error_message, None

            # Validate line field
            if field_type.get('type') == 'line':
                for field_value in field_values:
                    if '\n' in field_value:
                        error_message = f'value "{field_value}" of line type '\
                                        f'field "{field_name}" contains a '\
                                        f'newline character'
                        return error_message, None

            # Validate date field
            if field_type.get('type') == 'date':
                for field_value in field_values:
                    try:
                        _ = parser.parse(field_value)
                    except:
                        error_message = f'cannot parse date value '\
                                        f'"{field_value}" of field '\
                                        f'"{field_name}"'
                        return error_message, None

            # Validate bool field
            if field_type.get('type') == 'bool':
                for field_value in field_values:
                    if field_value not in ['0', '1', 'true',
                                           'false', 'yes', 'no']:
                        error_message = f'Value {field_value} for bool '\
                                        f'field {field_name} is not allowed'
                        return error_message, None

            # Validate real field
            if field_type.get('type') == 'real':
                processed_record[field_name] = []
                for field_value in field_values:
                    try:
                        num_value = float(field_value)
                        processed_record[field_name].append(num_value)
                    except ValueError:
                        error_message = f'can\'t convert value '\
                                        f'\"{field_value}\" of field '\
                                        f'\"{field_name}\" to a float'
                        return error_message, None

            # Validate range field
            if field_type.get('type') == 'range':
                max_value = field_type.get('max')
                min_value = field_type.get('min')
                processed_record[field_name] = []
                for field_value in field_values:
                    try:
                        if field_value[:2] == '0x' or field_value[:3] == '-0x':
                            num_value = get_hex_int(field_value)
                            processed_record[field_name].append(num_value)
                        else:
                            num_value = int(field_value)
                            processed_record[field_name].append(num_value)
                    except ValueError:
                        error_message = f"can't convert value "\
                                        f"\"{field_value}\" of field "\
                                        f"\"{field_name}\" to a float"
                        return error_message, None
                    if isinstance(max_value, int) and num_value > max_value:
                        error_message = f'Value {field_value} of field '\
                                        f'{field_name} exceeds the maximum '\
                                        f'range value {max_value}'
                        return error_message, None
                    if isinstance(min_value, int) and num_value < min_value:
                        error_message = f'Value {field_value} of field '\
                                        f'{field_name} is below the minimum '\
                                        f'range value {min_value}'
                        return error_message, None

            # Validate enum field
            if field_type.get('type') == 'enum':
                allowed_values = field_type.get('values', [])
                for field_value in field_values:
                    if field_value not in allowed_values:
                        error_message = f'value {field_value} of field '\
                                        f'{field_name} is not in allowed '\
                                        f'values {allowed_values}'
                        return error_message, None

            # Validate size field
            if field_type.get('type') == 'size':
                size_limit = field_type['limit']
                for field_value in field_values:
                    if len(field_value) > size_limit:
                        error_message = f'Value {field_value} of field '\
                                        f'{field_name} is above the field\'s '\
                                        f'size limit of {size_limit} '\
                                        f'characters'
                        return error_message, None

            # Validate regexp field
            if field_type.get('type') == 'regexp':
                pattern = field_type['pattern']
                for field_value in field_values:
                    if not re.match(pattern, field_value):
                        error_message = f'value "{field_value}" of field '\
                                        f'{field_name} does not match '\
                                        f'regex {pattern}'
                        return error_message, None

            # Validate uuid field
            if field_type.get('type') == 'uuid':
                for field_value in field_values:
                    if not re.match(UUID_PATTERN, field_value):
                        error_message = f'value "{field_value}" of uuid '\
                                        f'field {field_name} is not a '\
                                        f'valid UUID4'
                        return error_message, None

            # Auto-generate field values if needed
            for auto_field in self.config.get('auto', []):

                # Only auto-generate a field value if one doesn't already exist
                if not record.get(auto_field):

                    auto_field_type = self.config.get('field_types', {}).get(
                        auto_field)
                    if auto_field_type.get('type') == 'custom':
                        auto_field_type = self.config.get(
                            'custom_types', {}).get(auto_field_type['name'])

                    if auto_field_type.get('type') == 'date':
                        timestamp = datetime.now().strftime('%Y-%m-%d')
                        processed_record[auto_field] = [timestamp]

                    elif auto_field_type.get('type') == 'int':
                        max_field_value = max([max(r[auto_field])
                                               for r in self.records])
                        new_value = max_field_value + 1
                        processed_record[auto_field] = [new_value]

                    elif auto_field_type.get('type') == 'uuid':
                        new_uuid = uuid.uuid4()
                        processed_record[auto_field] = [new_uuid]

                    else:
                        error_message = f'Cannot auto-generate a value for '\
                                        f'field {auto_field} of type '\
                                        f'{auto_field_type.get("type")}'
                        return error_message, None

        # Validate Mandatory Fields
        for mandatory_field in self.config.get('mandatory', []):
            if mandatory_field not in processed_record.keys():
                return f'Missing mandatory field {mandatory_field}', None

        # Validate Unique Fields
        for unique_field in self.config.get('unique', []):
            if len(processed_record.get(unique_field, [])) > 1:
                error_message = f'More than 1 value found for '\
                                f'unique field {unique_field}'
                return error_message, None

        # Validate Allowed Fields
        allowed_fields = self.config.get('allowed')
        if allowed_fields:
            for field_name in processed_record.keys():
                if field_name not in allowed_fields:
                    error_message = f'field {field_name} not in allowed '\
                                    f'fields {allowed_fields}'
                    return error_message, None

        # Validate Prohibited Fields
        prohibited_fields = self.config.get('prohibit', [])
        for prohibited_field in prohibited_fields:
            if prohibited_field in processed_record.keys():
                error_message = f'prohibited field {prohibited_field} '\
                                f'present in record'
                return error_message, None

        # validate record set size constraint only if it is a less than or
        # less than or equal to constraint
        size_condition = self.config.get('size', {}).get('condition')
        if size_condition in ['<', '<=']:
            size_limit = self.config.get('size', {}).get('amount')
            if size_condition == '<=':
                size_limit = size_limit + 1
            if len(self.records) > size_limit:
                error_message = f'adding another record will exceed '\
                                f'the size limit of {size_limit} '\
                                f'in the record set'
                return error_message, None

        for field_name, field_values in processed_record.items():
            # Add a new field to the field list
            if not self.fields.get(field_name):
                self.fields[field_name] = True

        return False, processed_record

    def validate_size_constraint(self):
        size_constraint = self.config.get('size')
        if not size_constraint:
            return
        constraint_condition = size_constraint.get('condition')
        current_length = len(self.records)
        constraint_amount = size_constraint.get('amount')
        if constraint_condition == '==' and \
                current_length != constraint_amount:
            raise ValueError(f'Record set must have {constraint_amount} '
                             f'records but has {current_length}')
        elif constraint_condition == '<' and \
                current_length >= constraint_amount:
            raise ValueError(f'Record set must have less than '
                             f'{constraint_amount} records but has '
                             f'{current_length}')
        elif constraint_condition == '<=' and \
                current_length > constraint_amount:
            raise ValueError(f'Record set must have {constraint_amount} '
                             f'records or less but has {current_length}')
        elif constraint_condition == '>' and \
                current_length <= constraint_amount:
            raise ValueError(f'Record set must have more than '
                             f'{constraint_amount} records but has '
                             f'{current_length}')
        elif constraint_condition == '>=' and \
                current_length < constraint_amount:
            raise ValueError(f'Record set must have {constraint_amount} '
                             f'records or more but has {current_length}')

    def insert(self, records):
        '''Insert raw dictionaries into the record set
        Typically only called by internal methods
        '''
        for record in records:
            error_message, processed_record = self.validate_record(record)
            if not error_message:
                primary_key_field = self.config.get('key')
                primary_key_value = str(processed_record.get(
                    primary_key_field, [None])[0])
                if primary_key_field:
                    self.records[primary_key_value] = processed_record
                else:
                    if len(self.records.keys()):
                        primary_key_value = str(len(self.records.keys()) + 1)
                    else:
                        primary_key_value = 1
                    self.records[primary_key_value] = processed_record
            else:
                raise ValueError(f'Validation Error: {error_message} '
                                 f'in record {record}')

        # Check that size constraints are still met
        self.validate_size_constraint()

    def get_rec(self, include_config=False):
        '''Serialize the record set to recfile format
        '''

        # Write config to string
        if include_config:
            raise NotImplementedError()
        # Write records to string
        record_strings = []
        for record in self.records.values():
            record_string = ''
            for key, values in record.items():
                for value in values:
                    clean_value = str(value).replace("\n", "\n+ ")
                    record_string += f'{key}: {clean_value}\n'
            record_string = record_string.strip()
            record_strings.append(record_string)
        output_string = '\n\n'.join(record_strings)
        return output_string

    def save_rec(self, file_path):
        '''Write the contents of the record set to a file in recfile format
        '''
        raise NotImplementedError()

    def insert_rec(self, records_string):
        '''Insert one or more new records into the record set from a string
        in recfile format
        '''
        raise NotImplementedError()

    def get_csv(self, value_separator='|', include_headers=True):
        '''Serialize the record set to a string of CSV data
        '''
        csv_string = StringIO()
        writer = csv.DictWriter(csv_string, fieldnames=self.get_fields())
        if include_headers:
            writer.writeheader()
        for record in self.records.values():
            processed_record = {}
            for key, values in record.items():
                processed_record[key] = value_separator.join(
                    [str(value)
                     for value in values])
            writer.writerow(processed_record)
        return csv_string.getvalue()

    def insert_csv(self, csv_data, delimiter=',', value_separator=None):
        '''Import CSV data to update the record set
        '''

        f = StringIO(csv_data)
        reader = csv.DictReader(f, delimiter=delimiter)
        all_rows = []
        for row in reader:
            processed_row = {}
            for key, value in dict(row).items():
                if value_separator:
                    processed_row[key] = value.split(value_separator)
                else:
                    processed_row[key] = [value]
            all_rows.append(processed_row)
        self.insert(all_rows)

    def get_json(self):
        '''serialize the record set to a JSON string
        '''
        return json.dumps(list(self.records.values()))

    def insert_json(self, json_data):
        '''Import JSON data to update the record set
        '''
        records = json.loads(json_data)
        if not isinstance(records, list):
            raise ValueError(f'Records added in JSON format must be '
                             f'submitted as an array of objects, '
                             f'not as {type(records)}')
        clean_records = []
        for record in records:
            clean_record = {}
            if not isinstance(record, dict):
                raise ValueError(f'Each record added must be a JSON object. '
                                 f'Object of type {type(record)} found: '
                                 f'{record}')
            for key, value in record.items():
                if isinstance(value, list):
                    clean_record[key] = value
                elif not isinstance(key, str) or not isinstance(value, str):
                    raise ValueError('All keys and values in JSON imported '
                                     'data must be provided as strings')
                else:
                    clean_record[key] = [value]
            clean_records.append(clean_record)

        self.insert(clean_records)

    def get_fields(self):
        '''Get all of the fields present in the record set
        '''
        return list(self.fields.keys())

    def get_config(self):
        '''Get the config for the record set
        '''
        return self.config

    def get_record_count(self):
        '''Get the total number of records in the record set
        '''
        return len(self.records.values())

    def all(self):
        '''Get all records in the record set as a list of dictionaries
        '''
        return self.records.values()
