package com.ruoyi.visualization.mapper;

import org.apache.ibatis.annotations.Param;

import java.util.List;
import java.util.Map;

public interface VisiualizationDataMapper {

    /**
     * 获取xml原始数据
     * @param id 标签id
     * @return 数据信息
     */
    Map<String,String> queryRawData(@Param("id") String id);


    List<Map<String,String>> queryPrediction();

    /**
     * 查询所有不同的epoch id组
     * @return id列表
     */
    List<String> queryAllEpochIds();

    /**
     * 查询所有epoch结果
     * @return epoch结果列表
     */
    List<Map<String,Object>> queryEpochResults();

    /**
     * 按指定id分组查询epoch结果
     * @param id 分组id
     * @return epoch结果列表
     */
    List<Map<String,Object>> queryEpochResultsByGroup(@Param("id") String id);

    /**
     * 查询数据集列表
     * @return 数据集列表
     */
    List<Map<String,Object>> queryDatasetList();
}
