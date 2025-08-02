from flask import Flask, render_template, request, jsonify, redirect, url_for
from google.cloud import ndb
import json
from datetime import datetime

app = Flask(__name__)

# Initialize NDB client for App Engine
ndb_client = ndb.Client()

class PromptTemplate(ndb.Model):
    """Model for storing prompt templates"""
    name = ndb.StringProperty(required=True)
    description = ndb.TextProperty()
    template = ndb.TextProperty(required=True)
    category = ndb.StringProperty(default="General")
    tags = ndb.StringProperty(repeated=True)
    variables = ndb.JsonProperty()  # Store template variables as JSON
    created_date = ndb.DateTimeProperty(auto_now_add=True)
    modified_date = ndb.DateTimeProperty(auto_now=True)
    usage_count = ndb.IntegerProperty(default=0)

@app.route('/')
def index():
    """Main page showing all prompt templates"""
    with ndb_client.context():
        templates = PromptTemplate.query().order(-PromptTemplate.created_date).fetch()
        categories = list(set([t.category for t in templates]))
    return render_template('index.html', templates=templates, categories=categories)

@app.route('/template/<int:template_id>')
def view_template(template_id):
    """View a specific template"""
    with ndb_client.context():
        template = PromptTemplate.get_by_id(template_id)
        if not template:
            return "Template not found", 404
    return render_template('template_detail.html', template=template)

@app.route('/create', methods=['GET', 'POST'])
def create_template():
    """Create a new prompt template"""
    if request.method == 'POST':
        with ndb_client.context():
            # Extract variables from template using simple regex
            import re
            template_text = request.form['template']
            variables = re.findall(r'\{\{(\w+)\}\}', template_text)
            
            template = PromptTemplate(
                name=request.form['name'],
                description=request.form['description'],
                template=template_text,
                category=request.form['category'],
                tags=request.form['tags'].split(',') if request.form['tags'] else [],
                variables=variables
            )
            template.put()
        return redirect(url_for('index'))
    
    return render_template('create_template.html')

@app.route('/edit/<int:template_id>', methods=['GET', 'POST'])
def edit_template(template_id):
    """Edit an existing template"""
    with ndb_client.context():
        template = PromptTemplate.get_by_id(template_id)
        if not template:
            return "Template not found", 404
        
        if request.method == 'POST':
            import re
            template_text = request.form['template']
            variables = re.findall(r'\{\{(\w+)\}\}', template_text)
            
            template.name = request.form['name']
            template.description = request.form['description']
            template.template = template_text
            template.category = request.form['category']
            template.tags = request.form['tags'].split(',') if request.form['tags'] else []
            template.variables = variables
            template.put()
            return redirect(url_for('view_template', template_id=template_id))
    
    return render_template('edit_template.html', template=template)

@app.route('/api/search')
def search_templates():
    """API endpoint to search templates"""
    query = request.args.get('q', '').lower()
    category = request.args.get('category', '')
    tag = request.args.get('tag', '')
    
    with ndb_client.context():
        templates_query = PromptTemplate.query()
        
        if category:
            templates_query = templates_query.filter(PromptTemplate.category == category)
        
        templates = templates_query.fetch()
        
        # Filter by search query and tags in Python (since NDB has limited text search)
        filtered_templates = []
        for template in templates:
            if query and query not in template.name.lower() and query not in template.description.lower():
                continue
            if tag and tag not in template.tags:
                continue
            filtered_templates.append(template)
        
        # Convert to dict for JSON response
        result = []
        for template in filtered_templates:
            result.append({
                'id': template.key.id(),
                'name': template.name,
                'description': template.description,
                'category': template.category,
                'tags': template.tags,
                'created_date': template.created_date.isoformat() if template.created_date else None
            })
    
    return jsonify(result)

@app.route('/api/render/<int:template_id>', methods=['POST'])
def render_template_api(template_id):
    """API endpoint to render a template with provided variables"""
    with ndb_client.context():
        template = PromptTemplate.get_by_id(template_id)
        if not template:
            return jsonify({'error': 'Template not found'}), 404
        
        # Get variables from request
        variables = request.json if request.json else {}
        
        # Render template using Jinja2
        from jinja2 import Template
        try:
            jinja_template = Template(template.template)
            rendered = jinja_template.render(**variables)
            
            # Increment usage count
            template.usage_count += 1
            template.put()
            
            return jsonify({
                'rendered': rendered,
                'template_name': template.name,
                'variables_used': list(variables.keys())
            })
        except Exception as e:
            return jsonify({'error': f'Template rendering error: {str(e)}'}), 400

@app.route('/delete/<int:template_id>', methods=['POST'])
def delete_template(template_id):
    """Delete a template"""
    with ndb_client.context():
        template = PromptTemplate.get_by_id(template_id)
        if template:
            template.key.delete()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
