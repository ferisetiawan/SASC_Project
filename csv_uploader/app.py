from flask import Flask, request, render_template, jsonify, send_file
import pandas as pd
import os
import glob

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploaded_files'

def clear_upload_folder():
    files = glob.glob(os.path.join(app.config['UPLOAD_FOLDER'], '*'))
    for f in files:
        os.remove(f)

# Create the upload folder if it does not exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Clear the upload folder when the app starts
clear_upload_folder()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'})
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'})
    if file and file.filename.endswith('.csv'):
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'saved_dataframe.csv')
        file.save(file_path)

        # Load the CSV file into a DataFrame
        df = pd.read_csv(file_path)

        # Convert 'Y' and 'N' to numerical values for 'SESSION DONE' and 'ATTENDANCE STATUS'
        df['SESSION DONE'] = df['SESSION DONE'].map({'Y': 1, 'N': 0})
        df['ATTENDANCE STATUS'] = df['ATTENDANCE STATUS'].map({'Y': 1, 'N': 0})

        # Force the NIM column to be string and SESSION, WEEK columns to be integers without decimal places
        df['NIM'] = df['NIM'].astype(str)
        df['SESSION'] = df['SESSION'].astype(int)
        df['WEEK'] = df['WEEK'].astype(int)

        # Save the modified DataFrame back to the CSV
        df.to_csv(file_path, index=False)

        return jsonify({'success': 'File uploaded'})
    else:
        return jsonify({'error': 'Invalid file format'})

@app.route('/get_dataframe')
def get_dataframe():
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'saved_dataframe.csv')
    if os.path.exists(file_path):
        df = pd.read_csv(file_path)
        df_html = df.to_html(classes='table table-striped', index=False)
        return jsonify({'data': df_html})
    else:
        return jsonify({'error': 'No DataFrame available'})

@app.route('/aggregate_by_nim', methods=['POST'])
def aggregate_by_nim():
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'saved_dataframe.csv')
    if os.path.exists(file_path):
        try:
            df = pd.read_csv(file_path)

            # Ensure 'SESSION DONE' and 'ATTENDANCE STATUS' columns are properly handled
            df['SESSION DONE'] = df['SESSION DONE'].astype(int)
            df['ATTENDANCE STATUS'] = df['ATTENDANCE STATUS'].astype(int)

            # Group by 'NIM' and calculate the sum of 'SESSION DONE' and 'ATTENDANCE STATUS'
            grouped = df.groupby(['NIM', 'Binusian ID', 'NAMA']).agg({
                'SESSION DONE': 'sum',
                'ATTENDANCE STATUS': 'sum'
            }).reset_index()

            # Clear data with SUM_SESSION = 0
            grouped_clean = grouped[grouped['SESSION DONE'] >= 5].copy()

            # Calculate the ratio of (SUM) SESSION DONE to (SUM) ATTENDANCE STATUS
            grouped_clean['Ratio'] = grouped_clean.apply(lambda row: (row['ATTENDANCE STATUS'] / row['SESSION DONE']) if row['ATTENDANCE STATUS'] != 0 else 0, axis=1)

            # Convert Ratio to percentage with three decimals and add '%' symbol
            grouped_clean['Ratio'] = (grouped_clean['Ratio'] * 100).round(3).astype(str) + '%'

            # Rename the columns for clarity
            grouped_clean.columns = ['NIM', 'Binusian ID', 'NAMA', 'SUM_SESSION', 'SUM_ATTENDANCE', 'Ratio']

            NIM_aggregate = grouped_clean[grouped_clean['Ratio'].str.replace('%', '').astype(float) < 85.0]

            # Save the aggregated DataFrame
            aggregated_file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'nim_aggregate.csv')
            NIM_aggregate.to_csv(aggregated_file_path, index=False)

            # Debugging output
            print("Aggregated DataFrame:")
            print(NIM_aggregate)

            return jsonify({'success': 'Aggregation completed'})
        except Exception as e:
            return jsonify({'error': str(e)})
    else:
        return jsonify({'error': 'No DataFrame available'})

@app.route('/get_nim_aggregate')
def get_nim_aggregate():
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'nim_aggregate.csv')
    if os.path.exists(file_path):
        df = pd.read_csv(file_path)
        df_html = df.to_html(classes='table table-striped', index=False)
        return jsonify({'data': df_html})
    else:
        return jsonify({'error': 'No NIM Aggregate DataFrame available'})

@app.route('/aggregate_by_nim_course', methods=['POST'])
def aggregate_by_nim_course():
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'saved_dataframe.csv')
    if os.path.exists(file_path):
        try:
            df = pd.read_csv(file_path)

            # Ensure 'SESSION DONE' and 'ATTENDANCE STATUS' columns are properly handled
            df['SESSION DONE'] = df['SESSION DONE'].astype(int)
            df['ATTENDANCE STATUS'] = df['ATTENDANCE STATUS'].astype(int)

            # Group by 'NIM' and 'COURSE NAME' and calculate the sum of 'SESSION DONE' and 'ATTENDANCE STATUS'
            grouped = df.groupby(['NIM', 'COURSE NAME']).agg({
                'SESSION DONE': 'sum',
                'ATTENDANCE STATUS': 'sum'
            }).reset_index()

            # Rename columns for clarity
            grouped.columns = ['NIM', 'COURSE NAME', 'Sum_Session_Done', 'Sum_Attendance_Status']

            grouped['Ratio'] = grouped['Sum_Attendance_Status'] / grouped['Sum_Session_Done']

            # Convert Ratio to percentage with three decimals and add '%' symbol
            grouped['Ratio'] = (grouped['Ratio'] * 100).round(3).astype(str) + '%'

            # Merge with original dataframe to get 'Binusian ID' and 'NAMA'
            grouped = grouped.merge(df[['NIM', 'Binusian ID', 'NAMA']].drop_duplicates(), on='NIM', how='left')

            # Reorder columns for clarity
            grouped = grouped[['NIM', 'Binusian ID', 'NAMA', 'COURSE NAME', 'Sum_Session_Done', 'Sum_Attendance_Status', 'Ratio']]

            # Filter by ratio
            NIM_Course_aggregate = grouped[grouped['Ratio'].str.replace('%', '').astype(float) < 85.0]

            # Save the aggregated DataFrame
            aggregated_file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'nim_course_aggregate.csv')
            NIM_Course_aggregate.to_csv(aggregated_file_path, index=False)

            # Debugging output
            print("Aggregated DataFrame:")
            print(NIM_Course_aggregate)

            return jsonify({'success': 'Aggregation completed'})
        except Exception as e:
            return jsonify({'error': str(e)})
    else:
        return jsonify({'error': 'No DataFrame available'})

@app.route('/get_nim_course_aggregate')
def get_nim_course_aggregate():
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'nim_course_aggregate.csv')
    if os.path.exists(file_path):
        df = pd.read_csv(file_path)
        df_html = df.to_html(classes='table table-striped', index=False)
        return jsonify({'data': df_html})
    else:
        return jsonify({'error': 'No NIM Course Aggregate DataFrame available'})

@app.route('/export_to_excel/<string:filename>')
def export_to_excel(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(file_path):
        df = pd.read_csv(file_path)
        df.to_excel(file_path.replace('.csv', '.xlsx'), index=False)
        return send_file(file_path.replace('.csv', '.xlsx'), as_attachment=True, download_name=f"{filename}.xlsx")
    else:
        return jsonify({'error': 'File not found'})

if __name__ == '__main__':
    app.run(debug=True)
