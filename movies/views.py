from rest_framework import viewsets, status, permissions
from rest_framework.response import Response
from rest_framework.decorators import api_view
from .serializers import *
import urllib.request as ul
import os, json, ssl, pdb
from urllib.parse import quote
from pathlib import Path
from django.http import HttpRequest, HttpResponse
from .models import *
from django.shortcuts import get_object_or_404

# 영화진흥위원회 api key
def get_api_key(type):
  BASE_DIR = Path(__file__).resolve().parent.parent
  CREDENTIAL_FILE = os.path.join(BASE_DIR, 'credentials.json')
  credentials = json.loads(open(CREDENTIAL_FILE).read())

  if type is 'image':
    return credentials["NAVER_CLIENT_ID"], credentials["NAVER_CLIENT_SECRET"]
  elif type is 'detail':
    return credentials["MOVIE_DETAIL_API_KEY"]
  else:
    return credentials["MOVIE_API_KEY"]


# 영화 이미지 url
@api_view(['GET'])
def naver_api(request, movie_name):
  client_id, client_secret = get_api_key("image")
  query = quote(movie_name)

  url = "https://openapi.naver.com/v1/search/movie.json?query={}".format(query)
  request = ul.Request(url)
  request.add_header("X-Naver-Client-Id", client_id)
  request.add_header("X-Naver-Client-Secret",client_secret)
  context = ssl._create_unverified_context()

  response = ul.urlopen(request, context=context)
  rescode = response.getcode()

  if (rescode == 200):
    response_data = json.loads(response.read())
    image_url = json.dumps(response_data["items"][0]["image"]).replace('"', "") # Note: 첫 번째 검색 결과의 사진을 가져옴
    rating = json.dumps(response_data["items"][0]["userRating"]).replace('"', "")
    ret_json_obj = {'image_url': image_url, 'rating': rating}
    return HttpResponse(json.dumps(ret_json_obj))
  else:
    print("Error code: " + rescode)


# 영화목록
@api_view(['GET'])
def search(request, movie_name):
  key = get_api_key("list")
  query = quote(movie_name)

  url = "http://www.kobis.or.kr/kobisopenapi/webservice/rest/movie/searchMovieList.json?key={}&movieNm={}".format(key, query)
  url_request = ul.Request(url)

  response = ul.urlopen(url_request)
  rescode = response.getcode()

  if (rescode == 200):
    response_data = json.loads(response.read())

    # json 재구성
    items = []
    movie_list = response_data["movieListResult"]["movieList"]

    for i in range(response_data["movieListResult"]["totCnt"]):
      movie = {}
      movie["movieCode"] = movie_list[i]["movieCd"]
      naver_api_result = json.loads(naver_api(request._request, movie_list[i]["movieNm"]).content)
      movie["thumbnailUrl"] = naver_api_result["image_url"]
      movie["movie_name"] = movie_list[i]["movieNm"]
      movie["directors"] = movie_list[i]["directors"]
      movie["opening_date"] = movie_list[i]["openDt"]
      movie["genre"] = movie_list[i]["repGenreNm"]
      movie["running_time"] = int(json.loads(detail(request._request, movie_list[i]["movieCd"], 'running_time').content))
      movie["rating"] = naver_api_result["rating"]
      items.append(movie)

    ret_json_obj = {"items": items}
    return Response(data=ret_json_obj)
  else:
    print("Error code: " + rescode)


# 영화 상세정보
@api_view(['GET'])
def detail(request, movie_cd, specific=''):
  key = get_api_key("detail")
  
  url = "http://www.kobis.or.kr/kobisopenapi/webservice/rest/movie/searchMovieInfo.json?key={}&movieCd={}".format(key, movie_cd)

  request = ul.Request(url)

  response = ul.urlopen(request)
  rescode = response.getcode()

  if (rescode == 200):
    response_data = json.loads(response.read())

    if specific is 'running_time': # 상영시간 정보
      time = json.dumps(response_data["movieInfoResult"]["movieInfo"]["showTm"])
      return HttpResponse(time, content_type="text/json-comment-filtered")
    elif specific is 'title': # 영화제목
      title = json.dumps(response_data["movieInfoResult"]["movieInfo"]["movieNm"])
      return HttpResponse(title, content_type="text/json-comment-filtered")
    else: # 상세정보 전체
      return Response(data=response_data)
  else:
    print("Error code: " + rescode)
  

@api_view(['GET', 'post'])
def prediction(request):
  # 나의 평가를 기다리는 친구의 요청
  if request.method == 'GET':
    source_user_id = request.GET.get('uid')
    queryset = Prediction.objects.all().filter(target=source_user_id)
    serializer = PredictionSerializer(queryset, many=True)

    items = []

    for data in serializer.data:
      data = data["movie"]
      print(data)

      movie = {}
      movie["movieCode"] = data["movieCode"]
      movie["thumbnailUrl"] = data["thumbnailUrl"]
      movie["movie_name"] = data["movieName"]
      if type(data["directors"]) is list:
        movie["directors"] = data["directors"]
      else:
        movie["directors"] = [data["directors"]]
      movie["opening_date"] = data["openingDate"]
      movie["genre"] = data["genre"]
      movie["running_time"] = data["runningTime"]
      movie["rating"] = "9.39"

      items.append(movie)
    
    ret_json_obj = {"items": items}
    return Response(data=ret_json_obj)

  # 예측 생성
  elif request.method == 'POST':
    data = request.data
    movie_cd = data['movieCode']
    source_user_id = data['sourceUid']
    target_user_id = data['targetUid']
    value = data['rating']

    source_user = get_object_or_404(User, pk=source_user_id)
    target_user = get_object_or_404(User, pk=target_user_id)
    movie = Movie.objects.get(movie_code=movie_cd)

    Prediction.objects.create(source=source_user, target=target_user, movie=movie, value=value)
    prediction = Prediction.objects.last()

    serializer = PredictionSerializer(data=prediction)
    if serializer.is_valid():
      return Response(serializer.data, status=status.HTTP_201_CREATE)
    return Reesponse(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# recommend
@api_view(['GET'])
def recommend(request):
  items = []

  for i in range(5):
    movie = {}
    movie["movieCode"] = f'2021021{i+5}'
    items.append(movie)

  # 인셉션 인터스텔라 라라랜드 겨울왕국 조커
  items[0]["thumbnailUrl"] = "https://ssl.pstatic.net/imgmovie/mdi/mit110/1917/191735_P01_110003.jpg"
  items[0]["movie_name"] = "인셉션"
  items[0]["directors"] = [{"peopleNm": "크리스토퍼 놀란"}]
  items[0]["opening_date"] = "20100721"
  items[0]["genre"] = "드라마"
  items[0]["running_time"] = 147
  items[0]["rating"] = "9.61"

  items[1]["thumbnailUrl"] = "https://movie-phinf.pstatic.net/20160106_138/1452044846608eaFcJ_JPEG/movie_image.jpg"
  items[1]["movie_name"] = "인터스텔라"
  items[1]["directors"] = [{"peopleNm": "크리스토퍼 놀란"}]
  items[1]["opening_date"] = "20141106"
  items[1]["genre"] = "SF"
  items[1]["running_time"] = 169
  items[1]["rating"] = "9.12"

  items[2]["thumbnailUrl"] = "https://ssl.pstatic.net/imgmovie/mdi/mit110/1676/167613_P09_182225.jpg"
  items[2]["movie_name"] = "조커"
  items[2]["directors"] = [{"peopleNm": "토드 필립스"}]
  items[2]["opening_date"] = "20191002"
  items[2]["genre"] = "액션"
  items[2]["running_time"] = 122
  items[2]["rating"] = "8.97"

  items[3]["thumbnailUrl"] = "https://movie-phinf.pstatic.net/20201229_146/1609226288425JgdsP_JPEG/movie_image.jpg"
  items[3]["movie_name"] = "라라랜드"
  items[3]["directors"] = [{"peopleNm": "데이미언 셔젤"}]
  items[3]["opening_date"] = "20161207"
  items[3]["genre"] = "드라마"
  items[3]["running_time"] = 127
  items[3]["rating"] = "8.91"

  items[4]["thumbnailUrl"] = "https://movie-phinf.pstatic.net/20170418_82/1492496178995pHxdA_JPEG/movie_image.jpg"
  items[4]["movie_name"] = "겨울왕국"
  items[4]["directors"] = [{"peopleNm": "크리스 벅"}]
  items[4]["opening_date"] = "20140116"
  items[4]["genre"] = "애니메이션"
  items[4]["running_time"] = 108
  items[4]["rating"] = "9.20"


  ret_json_obj = {"items": items}

  return Response(data=ret_json_obj)

# old
@api_view(['GET'])
def old(request):
  items = []

  for i in range(5):
    movie = {}
    movie["movieCode"] = f'2021021{i+5}'
    items.append(movie)

  items[0]["thumbnailUrl"] = "https://movie-phinf.pstatic.net/20210107_160/1609984702837oNdmw_JPEG/movie_image.jpg"
  items[0]["movie_name"] = "소울"
  items[0]["directors"] = [{"peopleNm": "피트 닥터"}]
  items[0]["opening_date"] = "20210120"
  items[0]["genre"] = "애니메이션"
  items[0]["running_time"] = 107
  items[0]["rating"] = "9.37"

  items[1]["thumbnailUrl"] = "https://search.pstatic.net/common?type=o&amp;size=82x111&amp;quality=100&amp;direct=true&amp;src=https%3A%2F%2Fs.pstatic.net%2Fmovie.phinf%2F20210126_174%2F1611638248803840HH_JPEG%2Fmovie_image.jpg"
  items[1]["movie_name"] = "극장판 귀멸의 칼날: 무한열차편"
  items[1]["directors"] = [{"peopleNm": "소토자키 하루오"}]
  items[1]["opening_date"] = "20210127"
  items[1]["genre"] = "애니메이션"
  items[1]["running_time"] = 117
  items[1]["rating"] = "9.63"

  items[2]["thumbnailUrl"] = "https://ssl.pstatic.net/imgmovie/mdi/mit110/1960/196055_P08_174636.jpg"
  items[2]["movie_name"] = "어니스트 씨프"
  items[2]["directors"] = [{"peopleNm": "마크 윌리엄스"}]
  items[2]["opening_date"] = "20210203"
  items[2]["genre"] = "액션"
  items[2]["running_time"] = 98
  items[2]["rating"] = "9.56"

  items[3]["thumbnailUrl"] = "https://movie-phinf.pstatic.net/20210111_41/1610333478672K6ihS_JPEG/movie_image.jpg"
  items[3]["movie_name"] = "해피 투게더"
  items[3]["directors"] = [{"peopleNm": "왕가위"}]
  items[3]["opening_date"] = "20210204"
  items[3]["genre"] = "드라마"
  items[3]["running_time"] = 97
  items[3]["rating"] = "9.48"

  items[4]["thumbnailUrl"] = "https://movie-phinf.pstatic.net/20210114_78/1610588407942CoL2I_JPEG/movie_image.jpg"
  items[4]["movie_name"] = "세자매"
  items[4]["directors"] = [{"peopleNm": "이승원"}]
  items[4]["opening_date"] = "20210127"
  items[4]["genre"] = "드라마"
  items[4]["running_time"] = 115
  items[4]["rating"] = "8.91"


  ret_json_obj = {"items": items}

  return Response(data=ret_json_obj)


@api_view(['GET'])
def recent(request):
  items = []

  for i in range(5):
      movie = {}
      movie["movieCode"] = f'2021021{i}'
      items.append(movie)

  items[0]["thumbnailUrl"] = "https://ssl.pstatic.net/imgmovie/mdi/mit110/1917/191735_P01_110003.jpg"
  items[0]["movie_name"] = "인셉션"
  items[0]["directors"] = [{"peopleNm": "크리스토퍼 놀란"}]
  items[0]["opening_date"] = "20100721"
  items[0]["genre"] = "드라마"
  items[0]["running_time"] = 147
  items[0]["rating"] = "9.61"

  items[1]["thumbnailUrl"] = "https://movie-phinf.pstatic.net/20160106_138/1452044846608eaFcJ_JPEG/movie_image.jpg"
  items[1]["movie_name"] = "인터스텔라"
  items[1]["directors"] = [{"peopleNm": "크리스토퍼 놀란"}]
  items[1]["opening_date"] = "20141106"
  items[1]["genre"] = "SF"
  items[1]["running_time"] = 169
  items[1]["rating"] = "9.12"

  items[2]["thumbnailUrl"] = "https://movie-phinf.pstatic.net/20160901_187/1472711688297YP2jH_JPEG/movie_image.jpg"
  items[2]["movie_name"] = "포레스트 검프"
  items[2]["directors"] = [{"peopleNm": "로버트 저메키스"}]
  items[2]["opening_date"] = "19941015"
  items[2]["genre"] = "드라마"
  items[2]["running_time"] = 142
  items[2]["rating"] = "9.52"

  items[3]["thumbnailUrl"] = "https://ssl.pstatic.net/imgmovie/mdi/mit110/1676/167613_P09_182225.jpg"
  items[3]["movie_name"] = "조커"
  items[3]["directors"] = [{"peopleNm": "토드 필립스"}]
  items[3]["opening_date"] = "20191002"
  items[3]["genre"] = "액션"
  items[3]["running_time"] = 122
  items[3]["rating"] = "8.97"

  items[4]["thumbnailUrl"] = "https://movie-phinf.pstatic.net/20111223_57/13245799126671QMbI_JPEG/movie_image.jpg"
  items[4]["movie_name"] = "타짜"
  items[4]["directors"] = [{"peopleNm": "최동훈"}]
  items[4]["opening_date"] = "20060928"
  items[4]["genre"] = "범죄"
  items[4]["running_time"] = 139
  items[4]["rating"] = "9.19"

  ret_json_obj = {"items": items}
  return Response(data=ret_json_obj)


@api_view(['GET', 'post'])
def record(request):
    # 나의 기록 목록
    if request.method == 'GET':
        user_id = request.GET.get('uid')
        current_user = get_object_or_404(User, pk=user_id)

        queryset = Record.objects.all().filter(user=current_user)
        serializer = RecordSerializer(queryset, many=True)

        reviews = []

        for data in serializer.data:
          data = data["movie"]
          print(data)

          record = {}
          record["thumbnailUrl"] = data["thumbnailUrl"]
          record["movie_name"] = data["movieName"]
          record["rating"] = data["rating"]
          record["comment"] = data["comment"]

          reviews.append(record)
        
        ret_json_obj = {"reviews": reviews}
        return Response(data=ret_json_obj)
    
    # 새로운 기록
    elif request.method == 'POST':
        user_id = request.data['uid']
        current_user = get_object_or_404(User, pk=user_id)
        movie_cd = request.data['movieCode']
        count = Movie.objects.filter(movie_code=movie_cd).count() # db에 저장되어 있는 영화인지 확인
        if count == 0:
            # db에 영화 정보 저장
            print(json.loads(detail(request._request, movie_cd, 'title').content))
        
        movie = Movie.objects.get(movie_code=movie_cd)
        rating = request.data['rating']
        comment = request.data['comment']
        recommend = request.data['recommend']

        # 기록 생성
        Record.objects.create(user=current_user, movie=movie, rating=rating, comment=comment, recommend=recommend)

