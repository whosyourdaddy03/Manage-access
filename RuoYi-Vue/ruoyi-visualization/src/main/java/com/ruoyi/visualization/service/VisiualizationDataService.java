package com.ruoyi.visualization.service;

import com.alibaba.fastjson2.JSONArray;
import com.alibaba.fastjson2.JSONObject;
import jakarta.servlet.http.HttpServletResponse;

import java.awt.image.BufferedImage;
import java.io.IOException;

public interface VisiualizationDataService {

    /**
     * 获取xml原始数据
     * @param id 标签id
     * @return 数据信息
     */
    JSONObject queryRawData(String id);

    /**
     * 绘制图片
     * @param id 标签id
     * @param response 服务器响应对象
     */
    void queryPicture(String id, HttpServletResponse response) throws IOException;

    /**
     * 模型预测结果查询
     * @return
     */
    JSONArray queryPrediction();

    /**
     * 实时模型生成
     * @return
     */
    void generationModel();

    /**
     * 查询所有不同的epoch id组
     * @return id列表
     */
    JSONArray queryAllEpochIds();

    /**
     * 查询所有epoch结果
     * @return epoch结果列表
     */
    JSONArray queryEpochResults();

    /**
     * 按指定id分组查询epoch结果
     * @param id 分组id
     * @return epoch结果列表
     */
    JSONArray queryEpochResultsByGroup(String id);

    /**
     * 查询数据集列表
     * @return 数据集列表
     */
    JSONArray queryDatasetList();

    /**
     * 查询指定文件夹的图片列表(扫描本地目录)
     * @param folder 文件夹名(010或020)
     * @param pageNum 页码
     * @param pageSize 每页条数
     * @return 图片列表和总数
     */
    JSONObject queryImageList(String folder, int pageNum, int pageSize);

    /**
     * 获取原始图片(不绘制标注)
     * @param id 图片id
     * @param response 服务器响应对象
     */
    void getRawImage(String id, HttpServletResponse response) throws IOException;
}
