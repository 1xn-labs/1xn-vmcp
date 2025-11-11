import zipfile
import io
import csv
import xml.etree.ElementTree as ET
import logging

def get_mime_type(filename: str) -> str:
    """Get MIME type using mimetypes library on the original filename"""
    import mimetypes
    
    # Get MIME type using guess_type
    mime_type, encoding = mimetypes.guess_type(filename)
    
    # Return the detected MIME type or default if not detected
    return mime_type or 'application/octet-stream'

def convert_openxml_to_csv(file_content: bytes, filename: str) -> tuple[str, str]:
    """
    Convert OpenXML Excel file to CSV format
    Returns tuple of (csv_content, mime_type)
    """
    try:
        # Open the Excel file as a ZIP archive
        with zipfile.ZipFile(io.BytesIO(file_content)) as zip_file:
            # Find the workbook file
            workbook_path = None
            for name in zip_file.namelist():
                if name.endswith('workbook.xml'):
                    workbook_path = name
                    break
            
            if not workbook_path:
                return str(file_content), 'application/octet-stream'
            
            # Parse the workbook to get sheet names
            with zip_file.open(workbook_path) as workbook_file:
                workbook_tree = ET.parse(workbook_file)
                workbook_root = workbook_tree.getroot()
                
                # Extract namespace
                namespaces = {'w': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                
                # Get sheet names
                sheets = []
                for sheet in workbook_root.findall('.//w:sheet', namespaces):
                    sheet_name = sheet.get('name')
                    sheet_id = sheet.get('sheetId')
                    if sheet_name and sheet_id:
                        sheets.append((sheet_name, sheet_id))
            
            # Convert each sheet to CSV and concatenate
            csv_parts = []
            
            for sheet_name, sheet_id in sheets:
                # Find the sheet XML file
                sheet_path = f'xl/worksheets/sheet{sheet_id}.xml'
                if sheet_path not in zip_file.namelist():
                    continue
                
                # Parse the sheet XML
                with zip_file.open(sheet_path) as sheet_file:
                    sheet_tree = ET.parse(sheet_file)
                    sheet_root = sheet_tree.getroot()
                    
                    # Get shared strings if available
                    shared_strings = []
                    shared_strings_path = 'xl/sharedStrings.xml'
                    if shared_strings_path in zip_file.namelist():
                        with zip_file.open(shared_strings_path) as ss_file:
                            ss_tree = ET.parse(ss_file)
                            ss_root = ss_tree.getroot()
                            for si in ss_root.findall('.//w:t', namespaces):
                                shared_strings.append(si.text or '')
                    
                    # Extract data from sheet
                    rows = []
                    for row in sheet_root.findall('.//w:row', namespaces):
                        row_data = []
                        for cell in row.findall('.//w:c', namespaces):
                            cell_value = ''
                            v_elem = cell.find('.//w:v', namespaces)
                            if v_elem is not None and v_elem.text:
                                if cell.get('t') == 's':  # Shared string
                                    try:
                                        idx = int(v_elem.text)
                                        if idx < len(shared_strings):
                                            cell_value = shared_strings[idx]
                                    except (ValueError, IndexError):
                                        pass
                                else:  # Direct value
                                    cell_value = v_elem.text
                            row_data.append(cell_value)
                        if row_data:  # Only add non-empty rows
                            rows.append(row_data)
                    
                    # Convert to CSV
                    if rows:
                        csv_parts.append(f"=== Sheet: {sheet_name} ===\n")
                        csv_buffer = io.StringIO()
                        csv_writer = csv.writer(csv_buffer)
                        csv_writer.writerows(rows)
                        csv_parts.append(csv_buffer.getvalue())
                        csv_parts.append("\n")
            
            if csv_parts:
                csv_content = ''.join(csv_parts)
                return csv_content, 'text/csv'
            else:
                return str(file_content), 'application/octet-stream'
                
    except Exception as e:
        logger.warning(f"Failed to convert OpenXML file {filename} to CSV: {e}")
        return str(file_content), 'application/octet-stream'

    