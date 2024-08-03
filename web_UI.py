import gradio as gr
from sparkai.llm.llm import ChatSparkLLM, ChunkPrintHandler
from sparkai.core.messages import ChatMessage

import os
import tempfile
import shutil
import pandas as pd

import json
from datetime import datetime


log_content = ""
cancel_flag = False

def process_input(input_data, history, spark_api_url, spark_app_id, spark_api_key, spark_api_secret,
                  spark_llm_domain, streaming, max_tokens, request_timeout, top_k, text_Patch_id, API_temp):
    spark = ChatSparkLLM(
        spark_api_url=spark_api_url,
        spark_app_id=spark_app_id,
        spark_api_key=spark_api_key,
        spark_api_secret=spark_api_secret,
        spark_llm_domain=spark_llm_domain,
        streaming=streaming,
        max_tokens=int(max_tokens),
        request_timeout=int(request_timeout),
        top_k=int(top_k),
        model_kwargs={"patch_id": text_Patch_id},
        temperature = API_temp
    )
    print(max_tokens)
    print(API_temp)
    print(streaming)
    messages = [ChatMessage(role="user", content=input_data)]
    if streaming:
        a = spark.stream(messages)
        accumulated_text = ""
        for message in a:
            accumulated_text += message.content
            print(accumulated_text)
            yield accumulated_text
    else:
        response = spark.generate([messages])
        return response.generations[0][0].text if response else ""


def process_input_s(input_data, spark_api_url, spark_app_id, spark_api_key, spark_api_secret,
                  spark_llm_domain, streaming, max_tokens, request_timeout, top_k, text_Patch_id, API_temp):
    spark = ChatSparkLLM(
        spark_api_url=spark_api_url,
        spark_app_id=spark_app_id,
        spark_api_key=spark_api_key,
        spark_api_secret=spark_api_secret,
        spark_llm_domain=spark_llm_domain,
        streaming=streaming,
        max_tokens=int(max_tokens),
        request_timeout=int(request_timeout),
        top_k=int(top_k),
        model_kwargs={"patch_id": text_Patch_id},
        temperature = API_temp
    )
    messages = [ChatMessage(role="user", content=input_data)]
    response = spark.generate([messages])
    return response.generations[0][0].text if response else ""

def generate_file(file_obj, outputpath, text_prompt, spark_api_url, spark_app_id, spark_api_key, spark_api_secret,
                  spark_llm_domain, streaming, max_tokens, request_timeout, top_k, text_Patch_id, API_temp):
    
    global cancel_flag
    cancel_flag = False
    tmpdir = tempfile.mkdtemp()

    try:
        print('临时文件夹地址：{}'.format(tmpdir))
        FilePath = file_obj.name
        print('上传文件的地址：{}'.format(FilePath))

        global log_content
        # 将文件复制到临时目录中
        shutil.copy(file_obj.name, tmpdir)

        # 获取上传Gradio的文件名称
        FileName = os.path.basename(file_obj.name)
        print(FilePath)

        # 打开复制到新路径后的文件
        df = pd.read_csv(FilePath)

        # 检查是否存在output列，如果不存在则创建
        if 'output' not in df.columns:
            df['output'] = None

        # 处理每一行的input列
        for index, row in df.iterrows():

            if pd.notna(row['input']):

                if cancel_flag:  # 如果取消标志被设置，则退出循环
                    break

                input_F = text_prompt + f"{row['input']}"
                # print(input_F)
                
                processed_output = process_input_s(input_F, spark_api_url, spark_app_id, spark_api_key, spark_api_secret,
                                                    spark_llm_domain, streaming, max_tokens, request_timeout, top_k, text_Patch_id, API_temp)
                print(processed_output)
                # print(f"ok! This is the {index+1}th data processed.")
                now = datetime.now()
                log_content += f"""
{now}
当前接口信息:
APPID:{spark_app_id}
APIKey:{spark_api_key}
APISecret:{spark_api_secret}
Domain:{spark_llm_domain}
Patch_ID：{text_Patch_id}\n
"""
                log_content +="-"*80+f"{now}"+"-"*80+"\n"
                log_content += f"OUTPUT >> \n{processed_output} \n"
                log_content +="-"*80+f"{now}"+"-"*80+"\n"
                log_content += f"The {index+1}th data processed. \n"
                print(log_content)
                df.at[index, 'output'] = processed_output

        outputPath = os.path.join(tmpdir, os.path.splitext(FileName)[0] + "_processed" + ".csv")

        print("任务已完成！")
        log_content += "任务已完成！"
        df.to_csv(outputPath, index=False)
        # 返回新文件的地址
        return outputPath
    
    except Exception as e:
        log_content += f"Error occurred: {str(e)}\n"
    
    finally:
        cancel_flag = False
        shutil.rmtree('temp_dir', ignore_errors=True)


def generate_file_jsonl2csv(file_obj):    
    # 创建临时目录
    tmpdir_j2c = tempfile.mkdtemp()
    
    print('临时文件夹地址：{}'.format(tmpdir_j2c))
    print('上传文件的地址：{}'.format(file_obj.name))

    # 将文件复制到临时目录中
    shutil.copy(file_obj.name, tmpdir_j2c)

    # 获取上传Gradio的文件名称
    FileName = os.path.basename(file_obj.name)

    # 获取拷贝在临时目录的新的文件地址
    NewfilePath = os.path.join(tmpdir_j2c, FileName)
    print(NewfilePath)

    cleaned_lines = []
    with open(NewfilePath, 'r', encoding='utf-8') as file:
        for line in file:
            # 替换有问题的字符串
            line = line.replace('"true"', 'true')
            line = line.replace('"false"', 'false')
            cleaned_lines.append(line)

    # 将清理后的数据写回文件
    with open(NewfilePath, 'w', encoding='utf-8') as file:
        file.writelines(cleaned_lines)

    # 使用pandas读取jsonl文件
    df = pd.read_json(NewfilePath, lines=True)

    # 构造输出文件路径
    outputPath = os.path.join(tmpdir_j2c, "New" + os.path.splitext(FileName)[0] + ".csv")

    # 将DataFrame写入CSV文件
    df.to_csv(outputPath, index=False)  # index=False 表示不写入索引列

    # 返回新文件的地址
    return outputPath

def generate_file_csv2jsonl(file_obj):
    # 创建临时目录
    tmpdir_c2j = tempfile.mkdtemp()
    
    print('临时文件夹地址：{}'.format(tmpdir_c2j))
    print('上传文件的地址：{}'.format(file_obj.name))

    # 将文件复制到临时目录中
    shutil.copy(file_obj.name, tmpdir_c2j)

    # 获取上传Gradio的文件名称
    FileName = os.path.basename(file_obj.name)

    # 获取拷贝在临时目录的新的文件地址
    NewfilePath = os.path.join(tmpdir_c2j, FileName)
    print(NewfilePath)

    # 使用pandas读取CSV文件
    df = pd.read_csv(NewfilePath)

    # 构造输出文件路径
    outputPath = os.path.join(tmpdir_c2j, os.path.splitext(FileName)[0] + ".jsonl")

    # 将DataFrame写入JSON Lines文件
    with open(outputPath, 'w', encoding='utf-8') as f:
        for i, row in df.iterrows():
            json_row = row.to_dict()  # 将 Series 转换为字典
            json.dump(json_row, f, ensure_ascii=False)  # 使用 json.dump 直接写入文件
            f.write('\n')  # 

    # 返回新文件的地址
    return outputPath


def logput():

    return log_content

def set_cancel_flag():
    global cancel_flag
    cancel_flag = True
    log_content += "已终止！"
    

with gr.Blocks(
    title= "iFLYTEK_MaaS_toolbox",
    fill_height=True,
    theme="Base"
) as web_demo:
    gr.Markdown("## 🧰 [iFLYTEK_MaaS_toolbox](https://github.com/Fakerfigure/iFLYTEK_MaaS_toolbox)")
    with gr.Row():
        with gr.Column(scale=4, min_width=400):

            gr.Markdown("### 接口参数")
            text_URL = gr.Textbox(label="接口地址")
            text_APPID = gr.Textbox(label="APPID")
            text_APIKey = gr.Textbox(label="APIKey")
            text_APISecret = gr.Textbox(label="APISecret")
            text_Domain = gr.Textbox(label="Domain")
            text_Patch_id = gr.Textbox(label="Patch_ID")

            with gr.Row():
                text_User_ID = gr.Textbox(label="User_ID", value="spark_sdk_user")
                # text_timeout = gr.Textbox(label="Timeout", value=30)
                text_timeout = gr.Number(label="Timeout(s)",value=30, precision=0, minimum=0, maximum=60, step=10)
        
            gr.Markdown("### 模型配置参数")
            API_temp = gr.Slider(value=0.5, minimum=0.1, maximum=0.99, label='Temperature',step=0.1)
            with gr.Row():
                # text_Max_token = gr.Textbox(label="Max_token", value=4096)
                text_Max_token = gr.Number(label="Max_token",value=4096, precision=0, minimum=1024, maximum=8192,step=1024)
                text_Top_k=gr.Number(label="Top_k",value=4, precision=0, minimum=1, maximum=6)
                API_Stream = gr.Checkbox(label="Stream",value=True,interactive=False)

        with gr.Column(scale=10, min_width=600):
            with gr.Tab("单条测试"):
                gr.ChatInterface(
                    fn = process_input,
                    additional_inputs=[
                        text_URL, text_APPID, text_APIKey, text_APISecret, 
                        text_Domain, API_Stream, text_Max_token, text_timeout, 
                        text_Top_k, text_Patch_id, API_temp
                    ],
                    chatbot=gr.Chatbot(height=800)
                )
            with gr.Tab("批量测试"): 
                with gr.Column(scale=10, min_width=600):
                    gr.Markdown("**使用说明**: &nbsp;&nbsp; &#x2460;填写prompt(选择) &nbsp;&nbsp; &#x2461;上传文件")
                    outputs_path = gr.Textbox(label="输出路径(包含文件名!)",min_width = 500,visible= False)
                    text_prompt = gr.Textbox(label="Prompt",max_lines = 50,show_copy_button = True,min_width = 500,info = "若instruction和input已合并则不用填写")

                inputfile = gr.components.File(label="上传文件",height=50, scale = 2)
                outputfile = gr.components.File(label="下载文件",height=50, scale = 2)
                # log_output = gr.Textbox(label="Logs", interactive=False, lines=10)

                gr.Interface(
                    fn=generate_file, 
                    inputs=[
                        inputfile,
                        ],
                    additional_inputs=[
                    outputs_path,text_prompt,
                    text_URL, text_APPID, text_APIKey, text_APISecret, 
                    text_Domain, API_Stream, text_Max_token, text_timeout, 
                    text_Top_k, text_Patch_id, API_temp
                    ],
                    additional_inputs_accordion = gr.Accordion(label="不用配置", open=False, visible = False),
                    outputs = [outputfile], 
                    description="目前仅支持单个CSV，有且仅有‘input’列",
                )
                cancel_button = gr.Button("取消任务")
                cancel_button.click(fn=set_cancel_flag)
                gr.Interface(
                fn=logput,
                inputs=None,  # 不需要输入
                outputs=gr.Textbox(label="日志",interactive=False, lines=10,max_lines=10,text_align = "left"),  # 输出是文本
                live=True,  # 设置为实时更新
                allow_flagging = False,
            )
            with gr.Tab("小工具"): 
                with gr.Column(scale=10, min_width=600):
                    gr.Markdown("## JSONL转CSV")
                    gr.Interface(
                        fn=generate_file_jsonl2csv, 
                        inputs=gr.components.File(label="上传文件"), 
                        outputs=gr.components.File(label="下载文件"),
                    )
                with gr.Column(scale=10, min_width=600):
                    gr.Markdown("## CSV转JSONL")
                    gr.Interface(
                        fn=generate_file_csv2jsonl, 
                        inputs=gr.components.File(label="上传文件"), 
                        outputs=gr.components.File(label="下载文件"),
                    )
                gr.Markdown("## ⚙️ 其他小工具")
                with gr.Row():
                    gr.Markdown("- [JSON在线解析](https://www.json.cn/)")
                    gr.Markdown("- [Markdown在线编辑](https://pandao.github.io/editor.md/)")
                    gr.Markdown("- [PDF24 Tools](https://tools.pdf24.org/zh/)")
                    gr.Markdown("- [我的工具箱](https://toolgg.com/)")
    concurrency_limit = 10
web_demo.launch(
    share=True,
)
