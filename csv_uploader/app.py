from flask import Flask, request, render_template, jsonify, send_file
import pandas as pd
import numpy as np
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
        # Save the uploaded CSV file
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'uploaded_data.csv')
        file.save(file_path)

        # Load the CSV into a pandas DataFrame
        df = pd.read_csv(file_path)

        # Map values in "PRESENT" column: Y -> 1, N -> 0
        if 'PRESENT' in df.columns:
            df['PRESENT'] = df['PRESENT'].map({'Y': 1, 'N': 0})

        # Exclude rows where 'COURSE NAME' is one of the specified courses
        excluded_courses = ['Excellence Program I', 'English Plus Stage One', 'English Plus Stage Two']
        df = df[~df['COURSE NAME'].isin(excluded_courses)]

        # Store the full DataFrame, not just the selected columns
        df.to_csv(file_path, index=False)

        # Indicate success
        return jsonify({'success': 'File uploaded and stored successfully'})

    else:
        return jsonify({'error': 'Invalid file format'})

@app.route('/get_dataframe', methods=['GET'])
def get_dataframe():
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'uploaded_data.csv')

    if os.path.exists(file_path):
        # Load the full DataFrame
        df = pd.read_csv(file_path)

        # Filter to show only the desired columns
        filtered_columns = ["BINUSIAN ID", "NIM", "NAME", "MAJOR", "COMPONENT", "COURSE NAME", "SESSION ID NUM", "PRESENT"]

        if set(filtered_columns).issubset(df.columns):
            # Filter the DataFrame to only include the specific columns
            df_filtered = df[filtered_columns]

            # Convert filtered DataFrame to HTML for display
            df_html = df_filtered.to_html(classes='table table-striped', index=False)

            return jsonify({'data': df_html})
        else:
            return jsonify({'error': 'Required columns are missing from the CSV file'})
    else:
        return jsonify({'error': 'No data found'})

@app.route('/aggregate_by_nim', methods=['POST'])
def aggregate_by_nim():
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'uploaded_data.csv')
    if os.path.exists(file_path):
        try:
            df = pd.read_csv(file_path)

            # Map the SKS to the total possible sessions till the end of the semester
            def calculate_total_semester_sessions(sks):
                # Convert SKS to expected semester sessions: floor(SKS/2) * 13
                return (sks // 2) * 13

            # Assuming SKS is already present in the data, you may need to adjust based on your actual data
            if 'SKS' in df.columns:
                df['TOTAL_SEMESTER_SESSIONS'] = df['SKS'].apply(calculate_total_semester_sessions)

            # Group by NIM, NAME, and MAJOR to calculate total sessions and total present
            grouped = df.groupby(['NIM', 'NAME', 'MAJOR']).agg(
                TOTAL_PRESENT=('PRESENT', 'sum'),
                TOTAL_SESSIONS=('SESSION ID NUM', 'count'),  # Current sessions
                TOTAL_SEMESTER_SESSIONS=('TOTAL_SEMESTER_SESSIONS', 'sum')  # Expected sessions till semester end
            ).reset_index()

            # Filter out students with 0 total sessions
            grouped = grouped[grouped['TOTAL_SESSIONS'] > 0]

            # Calculate percentage of attendance based on current sessions
            grouped['PERCENTAGE_ATTENDANCE'] = (grouped['TOTAL_PRESENT'] / grouped['TOTAL_SESSIONS']) * 100

            # Calculate percentage attendance for the semester
            grouped['PERCENTAGE_ATTENDANCE_SEMESTER'] = (
                (grouped['TOTAL_PRESENT'] + (grouped['TOTAL_SEMESTER_SESSIONS'] - grouped['TOTAL_SESSIONS'])) /
                grouped['TOTAL_SEMESTER_SESSIONS']
            ) * 100

            # Format the percentage to two decimal places and add % sign
            grouped['PERCENTAGE_ATTENDANCE'] = grouped['PERCENTAGE_ATTENDANCE'].apply(lambda x: f'{x:.2f}%')
            grouped['PERCENTAGE_ATTENDANCE_SEMESTER'] = grouped['PERCENTAGE_ATTENDANCE_SEMESTER'].apply(lambda x: f'{x:.2f}%')

            # Exclude rows where PERCENTAGE_ATTENDANCE_SEMESTER is 100%
            grouped = grouped[grouped['PERCENTAGE_ATTENDANCE_SEMESTER'] != '100.00%']

            # Save the aggregated DataFrame
            aggregated_file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'nim_aggregate.csv')
            grouped.to_csv(aggregated_file_path, index=False)

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
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'uploaded_data.csv')
    if os.path.exists(file_path):
        try:
            df = pd.read_csv(file_path)

            # Group by 'NIM' and 'COURSE NAME' and calculate the count of 'PRESENT'
            grouped = df.groupby(['NIM', 'COURSE NAME']).agg({
                'PRESENT': 'sum'
            }).reset_index()

            # Rename columns for clarity
            grouped.columns = ['NIM', 'COURSE NAME', 'TOTAL_PRESENT']

            # Merge with original dataframe to get 'BINUSIAN ID' and 'NAME'
            grouped = grouped.merge(df[['NIM', 'BINUSIAN ID', 'NAME']].drop_duplicates(), on='NIM', how='left')

            # Reorder columns for clarity
            grouped = grouped[['NIM', 'BINUSIAN ID', 'NAME', 'COURSE NAME', 'TOTAL_PRESENT']]

            # Save the aggregated DataFrame
            aggregated_file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'nim_course_aggregate.csv')
            grouped.to_csv(aggregated_file_path, index=False)

            # Debugging output
            print("Aggregated DataFrame:")
            print(grouped)

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

@app.route('/filter_major', methods=['GET'])
def filter_major():
    major_search_term = request.args.get('major')

    if not major_search_term:
        return jsonify({'error': 'No search term provided'}), 400

    file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'uploaded_data.csv')

    if os.path.exists(file_path):
        df = pd.read_csv(file_path)

        # Filter the DataFrame by "MAJOR" column, case-insensitive search
        filtered_df = df[df['MAJOR'].str.contains(major_search_term, case=False, na=False)]

        # Convert the filtered DataFrame to HTML
        df_html = filtered_df.to_html(classes='table table-striped', index=False)
        return jsonify({'data': df_html})
    else:
        return jsonify({'error': 'No DataFrame available'})


if __name__ == '__main__':
    app.run(debug=True)
