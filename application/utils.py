import xlrd
import re
from shapely.geometry import Point

from pyspatialite import dbapi2 as db

from flask import flash

def flash(message,category):
    pass
    return True

def attribute_type_predictor(attribute_vals):
    """
    Pass a list of values and this function will predict what spatialite data type best matches the non-empty values in the list. The possible data types match those of an sqlite database.

    Returns a string 'TEXT','INTEGER', or 'REAL'
    """
    type_allowed=['TEXT','INTEGER','REAL']
    type_counts={}
    type_prediction='TEXT'
    type_counts_max=0
    for val in attribute_vals:
        #first test if the string representation of the value is not empty. we can only determine the type of value if something has been filled in. otherwise a column with only a few entries and for the rest empty values will look like a string (because empty stings are most common...) by converting to a string we also ensure that integer values like '0' will register as a filled in value while they would otherwise be false if we just tested using only 'if val:'
        try: val_str=str(val)
        except: val_str=''
        if val_str!='':
            #if the string repr is not empty, determine the type and add it to the type counts for this columns
            val_type=type(val).__name__
            flash('val_type=%s'%(val_type),'debug')
            #if your spreadsheet contains values like '10' python will think it's a float, even though we really prefer to store it as an integer. therefore, lets test if this float is really a float or just pretending to be..
            if val_type=='float':
                if val.is_integer():
                    val_type='INTEGER'
                else:
                    val_type='REAL'
            if val_type=='unicode' or val_type=='str':
                val_type="TEXT"
                try:
                    v=float(val)
                    if type(v).__name__=='float':
                        val_type='REAL'
                    else:
                        val_type='TEXT'
                except Exception as e:
                    val_type='TEXT'
            try: type_counts[val_type]+=1
            except KeyError as e: type_counts[val_type]=1 #key doesn't exist, add the first one
    for t in type_counts:
        if type_counts[t]>type_counts_max:
            type_counts_max=type_counts[t]
            type_prediction=t
    return type_prediction if type_prediction in type_allowed else 'TEXT' #text is the default!

def attribute_values_sanitizer(attribute_vals,data_type):
    """
    Pass a list of values and the datatype. This function will try to convert all of the values to said datatype and assign None when that fails. The list of values is then considered sanitized and can be used as input for data storage in the database.
    """
    return_values=[]
    for val in attribute_vals:
        if data_type=='TEXT':
            val_type=type(val).__name__
            if val_type=='str':
                try: val=str(val)
                except: val=None
            if val_type=='unicode':
                if type(val).__name__!='unicode': #this can occur if the overall type is unicode but we are passed a str like ''
                    try: val=unicode(val, "utf-8")
                    except: val=None
                val=None if not val else val
        if data_type=='REAL':
            try: val=float(val)
            except: val=None
        if data_type=='INTEGER':
            try: val=int(val)
            except: val=None
        return_values.append(val)
    return return_values

def attribute_uniques(attribute_vals):
    """
    Returns the number of unique non-None values. Can be used to estimate whether a data column contains categorical data. Maybe with a ratio of unique values/total values.
    """
    return len(set([v for v in attribute_vals if v != None]))


def excel_parser(filename,spatialite_file):
    #load the spatialite database where the points will be saved...
    tablenames=["fwo_metadata"]
    messages=[]
    conclusions=[]
    try:
        conn = db.connect(spatialite_file)
        cur = conn.cursor()
        try:
            cur.execute("SELECT InitSpatialMetadata(1)")
        except Exception:
            cur.execute("SELECT InitSpatialMetadata()")
        conn.commit()
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS fwo_metadata (
                name TEXT NOT NULL PRIMARY KEY,
                title TEXT NOT NULL,
                features INTEGER,
                description TEXT
            )
        """)
        conn.commit()
        flash("Loaded file <code>%s</code>"%(filename),"debug")
    except Exception as e:
        flash("Could not open or create metadata tables in sqlite file <code>%s</code>. Hint: %s"%(spatialite_file,e),"error")
        return (False,"Could not open or create metadata tables in sqlite file <code>%s</code>. Hint: %s"%(spatialite_file,e))
    try:
        book=xlrd.open_workbook(filename)
        sheets=book.sheet_names()
        flash("Found %i sheet(s): %s"%(len(sheets),"<code>"+"</code>,<code>".join(sheets)+"</code>"),"debug")
    except Exception as e:
        flash("Could not open the workbook <code>%s</code> with Python's xlrd module! Hint: %s"%(filename,e),"error")
        return (False,"Could not open the workbook <code>%s</code> with Python's xlrd module! Hint: %s"%(filename,e))

    for i,sheetname in enumerate(sheets):

        flash("Loading sheet %d: <code>%s</code>"%(i,sheetname),"debug")
        
        sheet=book.sheet_by_index(i)
        
        try:
            header_vals=sheet.row_values(0)
        except Exception as e:
            #flash("Could not load sheet <code>%s</code>!"%(sheetname),"error")
            #flash("Could not load sheet <code>%s</code>! Hint: %s"%(sheetname,e),"debug")
            header_vals=[]        

        lat_regex='^lat$|^lats$|^latitude|^y$|^ycoordinate$'
        lon_regex='^lon$|^lons$|^lngs$|^lng$|^longitude|^longtitude|^x$|^xcoordinate$'
        epsg=4326
        col_ix_lat=col_ix_lon=None


        #first sort out the headers by identifying a list of valid headers, as well as which headers and columns contain the coordinate information for the point.
        good_headers=[]
        bad_headers=[]
        header_list=[]
        
        for h in header_vals:
            try:
                test=str(h)
            except Exception as e:
                flash("The header cell <code>%s</code> contained strange characters! Make sure headers only contain only ASCII characters."%(h),"error")
                return (False,"The header cell <code>%s</code> contained strange characters! Make sure headers only contain only ASCII characters."%(h))

        for col_ix,header in enumerate(map(str,header_vals)):
            flash("Parsing header %d"%(col_ix),"debug")
            cleaned_header=header
            try:
                #Look for any additional info in parenthesis
                additional_info=re.search('\((.*?)\)',header).group(1)
            except Exception as e:
                additional_info=""
            finally:
                cleaned_header=re.sub('\((.*?)\)','',cleaned_header)

            try:
                epsg=int(re.search('^EPSG\:(\d+)',additional_info.upper()).group(1))
            except: pass

            try:
                #Look for units in square brackets
                units=re.search('\[(.*?)\]',cleaned_header).group(1)
            except Exception as e:
                units=""
            finally:
                cleaned_header=re.sub('\[(.*?)\]','',cleaned_header)

            try:
                cleaned_header=re.sub(r'\W+',' ',cleaned_header).lower()    #lowercase and remove non-word chars
                cleaned_header="_".join(map(str,cleaned_header.split()))    #replace any consecutive whitespace with _
                if cleaned_header not in good_headers and len(cleaned_header)>0:
                    #this is a valid header we want to use and turn into a data attribute!
                    good_headers.append(cleaned_header)
                    #data for this attribute
                    header_list.append({
                        'header':cleaned_header,
                        'original_header':header,
                        'additional_info':additional_info,
                        'units':units,
                        'column_index':col_ix,
                        'datatype':None,
                        'datavalues':[]
                    })
                    flash("Found header %s with info %s"%(cleaned_header,additional_info),"debug")
                    #if this header matches the regexp for defining the lat and lon
                    #colums, set the col_ix_lat or col_ix_lon variable which defines
                    #which column (i.e. item in header_list) is used for trying to
                    #make points later..
                    if not col_ix_lat and re.match(lat_regex,cleaned_header):
                        col_ix_lat=len(header_list)-1
                    if not col_ix_lon and re.match(lon_regex,cleaned_header):
                        col_ix_lon=len(header_list)-1
                else:
                    bad_headers.append({
                        'original_header':header,
                        'cleaned_header':cleaned_header,
                        'column_index':col_ix
                    })

            except Exception as e:
                return(False,"An unexpected error occurred while trying to parse header column <code>%i</code> in sheet <code>%s</code>. Extra hint: %s"%(col_ix,sheetname,e))

        if col_ix_lon==None or col_ix_lat==None:
            flash("Loaded sheet <code>%s</code> but could not find any valid latitude/longitude columns."%(sheetname),"error")
            conclusions.append("Warning: could not find any valid coordinates in sheet \"%s\""%(sheetname))
        else:
            flash("Loaded sheet <code>%s</code> and found latitude and longitude headers in columns <code>%i</code> and <code>%i</code>."%(sheetname,col_ix_lat,col_ix_lon),"debug")
            flash("Found %i headers that look good and will be turned into attributes of the data point. They are: %s"%(len(good_headers),"<code>"+"</code>, <code>".join(good_headers)+"</code>"),"debug")
            for h in bad_headers:
                flash("The header/attribute in column <code>%i</code> with value <code>%s</code> &nbsp;was ignored because it was empty, contained only strange characters, or was the same as another column header!"%(h["column_index"],h["cleaned_header"]),"debug")
            for ix,h in enumerate(header_list):
                attribute_vals=sheet.col_values(h["column_index"])
                h["datatype"]=attribute_type_predictor(attribute_vals[1:]) #don't include the header...
                h["attribute_values"]=attribute_values_sanitizer(attribute_vals[1:],h["datatype"])
                h["attribute_uniques"]=attribute_uniques(h["attribute_values"])
                flash("Values for attribute <code>%s</code> (in <code>header_list[%s]</code>) was predicted to have datatype <code>%s</code> with <code>%i</code> total entries, of which <code>%s</code> values were unique."%(h["header"],ix,h["datatype"],len(h["attribute_values"]),h["attribute_uniques"]),"debug")

            #create a table name for this sheet. the name needs to be unique in this database and not contain any funny characters. so, keep track of the tablenames we've used in the tablenames variable, and if a proposed table name exists already, keep appending a number to the end until it finds one that doesn't.
            tablename=re.sub(r'\W+',' ',sheetname).lower()
            tablename="fwo_"+"_".join(map(str,tablename.split()))
            proposed_tablename=tablename
            loop=1
            while proposed_tablename in tablenames:
                proposed_tablename="%s_%i"%(tablename,loop)
                loop+=1
            tablenames.append(proposed_tablename)
            tablename=proposed_tablename

            cur.execute("SELECT DiscardGeometryColumn('%s','geom');"%(tablename))
            conn.commit()

            cur.execute("DROP TABLE IF EXISTS '%s';"%(tablename))
            conn.commit()

            cur.execute("""
                CREATE TABLE %s (
                    'fwo_id' INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                    %s
                );
            """%(tablename,", ".join(["'%s' %s"%(h["header"],h["datatype"]) for h in header_list])))
            conn.commit()


            cur.execute("SELECT AddGeometryColumn('%s','geom', %s, 'POINT', 'XY');"%(tablename,epsg))
            conn.commit()

            cur.execute("DELETE FROM fwo_metadata WHERE name='%s';"%(tablename))
            conn.commit()

            cur.execute("INSERT INTO fwo_metadata (name,title) VALUES ('%s','%s');"%(tablename,sheetname))
            conn.commit()


            #compile a list of georeferenced points
            num_points=0
            for n,(lat,lon) in enumerate(zip(header_list[col_ix_lat]["attribute_values"],header_list[col_ix_lon]["attribute_values"])):
                try:
                    point=Point(lon,lat) #will raise an exception if lon,lat are None or some other incompatible value
                    attr_values=[header["attribute_values"][n] for header in header_list]
                    attr_names=",".join(["'"+header["header"]+"'" for header in header_list])
                    point_sql="INSERT INTO %s (%s,geom) VALUES (%s,GeomFromText('%s',%s))"%(tablename,attr_names,",".join("?"*len(attr_values)),point.wkt,epsg)
                    cur.execute(point_sql,attr_values)
                    num_points+=1
                except Exception as e:
                    flash("Failed to convert the feature in row <code>%i</code> to a valid point. Lat was <code>%s</code> and lon <code>%s</code>. Hint: %s"%(n+2,lat,lon,e),"error")
            conn.commit()
            description="<code>"+"</code> <code>".join(good_headers)+"</code>"
            cur.execute("""
            UPDATE fwo_metadata SET features=%s,description='%s' WHERE name='%s';
            """%(num_points,description,tablename))
            conn.commit()
            
            if num_points > 0:
                conclusions.append("Found %d points in sheet \"%s\"."%(num_points,sheetname))
            else:
                conclusions.append("Warning: Could not find any valid points in sheet \"%s\""%(sheetname))
            
    return (True," ".join(conclusions))
