
import io
from math import ceil
import zipfile
from celery import shared_task
import requests
import xml.etree.ElementTree as ET
from django.core.files.base import File

from judge.models.problem import Problem, ProblemGroup
from judge.models.problem_data import ProblemData, ProblemTestCase
from judge.models.profile import Profile


@shared_task
def parce_task_from_polygon(problem_code, problem_name, polygon_link, author_id):
	response = requests.post(polygon_link, data={
			"login": 'vasyamer',
			"password": '7ea7d6e7b4bf149f77f2ea1485e06f43',
			"type": "linux"
		})

	author = Profile.objects.get(id=author_id)
        
	if response.status_code != requests.codes.ok:
		raise Exception("Cannot download file")
	
	zip_file = io.BytesIO(response.content)
	problem_xml = ""
	with zipfile.ZipFile(zip_file, 'r') as zip_ref:
		problem_xml_file = zip_ref.open("problem.xml")
		problem_xml = problem_xml_file.read()
		problem_xml_file.close()
	
	problem_parser = ProblemXMLParser(problem_xml)
	
	problem = Problem()
	problem.code = problem_code
	problem.name = problem_name
	problem.description = ""
	problem.time_limit = problem_parser.get_time_limit()
	problem.memory_limit = problem_parser.get_memory_limit()
	problem.group = ProblemGroup.objects.get(name='Uncategorized')
	problem.points = 0
	problem.save()
	
	problem.authors.add(author)
	
	problem_data = ProblemData()
	problem_data.problem = problem
	problem_data.zipfile.save('problem.zip', File(zip_file))
	problem_data.save()
	
	for i, case in enumerate(problem_parser.get_tests()):
		p_case = ProblemTestCase()
		p_case.dataset = problem
		p_case.order = i + 1
		p_case.input_file = case["in"]
		p_case.output_file = case["out"]
		p_case.points = case["points"]
		p_case.is_pretest = False
		p_case.save()


class ProblemXMLParser:
    def __init__(self, xml_text: str) -> None:
        self.xml_text = xml_text
        self.root = ET.fromstring(xml_text)
        
    def get_problem_short_name(self) -> str:
        return self.root.get("short-name")
    
    def get_time_limit(self) -> float:
        miliseconds = int(self.root.find("judging/testset/time-limit").text)
        return miliseconds / 1000.0
    
    def get_memory_limit(self) -> float:
        bytes = int(self.root.find("judging/testset/memory-limit").text)
        return ceil(bytes / 1000)
    
    def get_tests(self):
        tests = []
        for testset in self.root.find("judging").iter("testset"):
            input_pattern = testset.find("input-path-pattern").text
            answer_pattern = testset.find("answer-path-pattern").text
            
            for i, test in enumerate(testset.iter("test")):                
                points = test.get("points", "0.0")
                is_sample = test.get("sample", "false")
                
                in_file = input_pattern % (i + 1,)
                ans_file = answer_pattern % (i + 1,)
                
                tests.append({
					"in": in_file,
					"out": ans_file,
					"points": round(float(points)),
					"sample": bool(is_sample),
				})
            
        return tests
    
    def get_yaml_dict(self):
        res = {
            "archive": "problem.zip",
			"test_cases": self.get_tests()
		}
        return res
         
